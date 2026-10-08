# DEVELOPER THANHTUNG · SECURE CORE
# Core hash analysis lives on Railway, not in browser HTML. SECURE-288.

import hashlib, math, re, statistics

MODULE_NAMES = (
    'NIBBLE-DIST','BYTE-DIST','PARITY-FLOW','SYMMETRY','POSITIONAL','MOD-FOLD',
    'SHA256-MIX','SHA3-MIX','BLAKE2-MIX','ROTATION','CHUNK-VOTE','CHECKSUM',
    'SHA512-MIX','MD5-MIX','MIRROR-XOR','HAMMING-FLOW','WINDOW-FLOW','AVALANCHE-MIX',
    'FAMILY-BALANCE','HALF-CROSS','QUARTER-FLOW','HISTOGRAM-SKEW','LAG-SPECTRAL',
    'SEGMENT-STABILITY','ENTROPY-BANDS','DIGEST-CONSENSUS','ROBUST-STACK',
    'HEX-RUN-PROFILE','PRIME-POS-FLOW','BITPLANE-SPECTRUM','CROSS-DIGEST-CORR',
    'MULTISCALE-BLOCK','PERMUTATION-VOTE','RESIDUE-ENSEMBLE','PERTURB-STABILITY',
    'META-CONSENSUS'
)

HEX_RE = re.compile(r'^[0-9a-f]+$')

def _clamp(v,a=-1.0,b=1.0): return min(b,max(a,float(v)))

def _mean(a):
    return sum(a)/len(a) if a else 0.0

def _trim(a, frac=.18):
    a=sorted(float(x) for x in a)
    if not a: return 0.0
    k=min(len(a)//3,int(len(a)*frac))
    b=a[k:len(a)-k] if len(a)-2*k>0 else a
    return _mean(b)

def _center(v,c,s):
    return _clamp((float(v)-float(c))/(float(s) or 1.0))

def _entropy(vals):
    if not vals: return 0.0
    counts={}
    for v in vals: counts[v]=counts.get(v,0)+1
    n=len(vals); h=0.0
    for c in counts.values():
        p=c/n
        h -= p*math.log2(p)
    den=math.log2(max(2,len(counts)))
    return h/den if den else 0.0

def _auto(vals, lag):
    if len(vals)<=lag or lag<=0: return 0.0
    a=vals[:-lag]; b=vals[lag:]
    ma=_mean(a); mb=_mean(b)
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return _clamp(num/(da*db)) if da and db else 0.0

def _trans_bool(vals):
    if len(vals)<2:return 0.0
    changes=sum(vals[i]!=vals[i-1] for i in range(1,len(vals)))
    return _center(changes/(len(vals)-1),.5,.5)

def _digest_bytes(name, data:bytes):
    if name=='sha3': return hashlib.sha3_256(data).digest()
    if name=='blake2': return hashlib.blake2b(data,digest_size=32).digest()
    if name=='sha512': return hashlib.sha512(data).digest()
    if name=='md5': return hashlib.md5(data).digest()
    return hashlib.sha256(data).digest()

def _eight(vals):
    vals=[_clamp(x) for x in vals]
    if not vals: vals=[0.0]
    while len(vals)<8:
        vals.append(_trim(vals))
    return vals[:8]

def _digest_group(d):
    n=list(d)
    return _eight([
        _center(_mean(n),127.5,90),
        _center(sum(n)%257,128,128),
        _center(sum(x&1 for x in n),len(n)/2,max(1,len(n)/2)),
        _auto(n,1),_auto(n,2),
        _center(_entropy(n),.88,.22),
        _center(_mean(n[:len(n)//2])-_mean(n[len(n)//2:]),0,70),
        _center(sum(bin(x).count('1') for x in n),4*len(n),2.4*len(n)),
    ])

def analyze_hash(value:str):
    z=(value or '').strip().lower()
    if len(z) not in (32,64) or not HEX_RE.fullmatch(z):
        raise ValueError('Hash phải là MD5 32 HEX hoặc SHA256 64 HEX')
    kind='MD5' if len(z)==32 else 'SHA256'
    nib=[int(c,16) for c in z]
    raw=bytes.fromhex(z)
    n=len(nib); b=len(raw)
    groups=[]

    # 1 NIBBLE-DIST
    groups.append(_eight([
        _center(_mean(nib),7.5,5),
        _center(sum(v>=8 for v in nib)/n,.5,.5),
        _center(sum(v&1 for v in nib)/n,.5,.5),
        _auto(nib,1),_auto(nib,2),_auto(nib,3),
        _center(_entropy(nib),.82,.24),
        _center(max(nib)-min(nib),12,5)
    ]))
    # 2 BYTE-DIST
    groups.append(_eight([
        _center(_mean(raw),127.5,90),
        _center(sum(raw)%257,128,128),
        _auto(list(raw),1),_auto(list(raw),2),
        _center(_entropy(list(raw)),.9,.2),
        _center(sum(x>127 for x in raw)/b,.5,.5),
        _center(sum(x&1 for x in raw)/b,.5,.5),
        _center(sum(bin(x).count('1') for x in raw),4*b,2.5*b),
    ]))
    # 3 PARITY-FLOW
    par=[v&1 for v in nib]
    groups.append(_eight([
        _center(_mean(par),.5,.5),_trans_bool(par),
        _auto(par,1),_auto(par,2),_auto(par,4),
        _center(sum(par[i]==par[i-1] for i in range(1,n)),(n-1)/2,(n-1)/2),
        _center(sum(par[::2])-sum(par[1::2]),0,n/3),
        _center(sum((v>>1)&1 for v in nib)/n,.5,.5)
    ]))
    # 4 SYMMETRY
    mir=[nib[i]^nib[-1-i] for i in range(n//2)]
    groups.append(_eight([
        _center(_mean(mir),7.5,5),_center(sum(v==0 for v in mir),len(mir)/16,max(1,len(mir)/5)),
        _auto(mir,1),_auto(mir,2),_center(_entropy(mir),.8,.3),
        _center(_mean(nib[:n//2])-_mean(nib[n//2:]),0,5),
        _center(sum(abs(nib[i]-nib[-1-i]) for i in range(n//2))/max(1,n//2),5.2,4),
        _center(sum((nib[i]+nib[-1-i])%2 for i in range(n//2))/max(1,n//2),.5,.5)
    ]))
    # 5 POSITIONAL
    groups.append(_eight([
        _center(_mean(nib[::2])-_mean(nib[1::2]),0,4),
        _center(_mean(nib[::3])-_mean(nib[1::3]),0,4),
        _center(_mean(nib[:8])-_mean(nib[-8:]),0,5),
        _center(sum((i+1)*v for i,v in enumerate(nib))%(n*16),n*8,n*8),
        _auto(nib,5),_auto(nib,7),
        _center(_mean([v for i,v in enumerate(nib) if i%4 in (0,3)])-7.5,0,4),
        _center(_mean([v for i,v in enumerate(nib) if i%4 in (1,2)])-7.5,0,4)
    ]))
    # 6 MOD-FOLD
    groups.append(_eight([
        _center(sum(nib)%16,7.5,7.5),_center(sum(raw)%256,127.5,127.5),
        _center(sum((i+1)*v for i,v in enumerate(nib))%97,48,48),
        _center(sum((i%7+1)*v for i,v in enumerate(nib))%113,56,56),
        _center(sum(v*v for v in nib)%127,63,63),
        _center(sum((v+1)*(i+3) for i,v in enumerate(nib))%131,65,65),
        _center(sum(raw[::2])%251,125,125),_center(sum(raw[1::2])%251,125,125)
    ]))

    # 7-8-9 digest mixes
    groups.append(_digest_group(_digest_bytes('sha256',raw)))
    groups.append(_digest_group(_digest_bytes('sha3',raw)))
    groups.append(_digest_group(_digest_bytes('blake2',raw)))

    # 10 ROTATION
    rots=[]
    for k in (1,3,5,7,11,13,17,19):
        rr=nib[k%n:]+nib[:k%n]
        rots.append(_center(sum((i+1)*v for i,v in enumerate(rr))%(16*n),8*n,8*n))
    groups.append(_eight(rots))
    # 11 CHUNK-VOTE
    size=max(4,n//8); chunks=[nib[i:i+size] for i in range(0,n,size)]
    groups.append(_eight([_center(_mean(c),7.5,4.5) for c in chunks]))
    # 12 CHECKSUM
    groups.append(_eight([
        _center(sum(nib)%31,15,15),_center(sum(raw)%63,31,31),
        _center(sum((i+1)*v for i,v in enumerate(nib))%127,63,63),
        _center(sum((i+5)*(v+1) for i,v in enumerate(nib))%251,125,125),
        _center(sum(x^i for i,x in enumerate(raw))%257,128,128),
        _center(sum((x+i)&255 for i,x in enumerate(raw))%257,128,128),
        _center(sum(bin(x).count('1') for x in raw)%37,18,18),
        _center(int.from_bytes(raw[:min(4,b)],'big')%101,50,50)
    ]))
    # 13 SHA512, 14 MD5
    groups.append(_digest_group(_digest_bytes('sha512',raw)))
    groups.append(_digest_group(_digest_bytes('md5',raw)))
    # 15 MIRROR-XOR
    groups.append(_eight([
        _center(_mean(mir),7.5,5),_auto(mir,1),_auto(mir,2),_auto(mir,3),
        _center(sum(mir)%31,15,15),_center(_entropy(mir),.8,.3),
        _center(sum(v>7 for v in mir)/max(1,len(mir)),.5,.5),_trans_bool([v>7 for v in mir])
    ]))
    # 16 HAMMING-FLOW
    hw=[bin(x).count('1') for x in raw]
    groups.append(_eight([
        _center(_mean(hw),4,2.2),_auto(hw,1),_auto(hw,2),_center(_entropy(hw),.75,.3),
        _center(sum(v>=4 for v in hw)/b,.5,.5),_trans_bool([v>=4 for v in hw]),
        _center(_mean(hw[:b//2])-_mean(hw[b//2:]),0,2),
        _center(sum(abs(hw[i]-hw[i-1]) for i in range(1,b))/max(1,b-1),2,2)
    ]))
    # 17 WINDOW-FLOW
    wins=[]
    for w in (4,6,8,10,12,16,20,24):
        if w<=n:wins.append(_center(_mean(nib[-w:]),7.5,4.5))
        else:wins.append(_center(_mean(nib),7.5,4.5))
    groups.append(_eight(wins))
    # 18 AVALANCHE-MIX
    dg=_digest_bytes('sha256',z.encode())
    av=[bin(a^b).count('1') for a,b in zip((raw*4)[:len(dg)],dg)]
    groups.append(_eight([
        _center(_mean(av),4,2.2),_auto(av,1),_auto(av,2),_center(_entropy(av),.78,.28),
        _center(sum(v>=4 for v in av)/len(av),.5,.5),_trans_bool([v>=4 for v in av]),
        _center(sum(av)%31,15,15),_center(max(av)-min(av),5,3)
    ]))

    scores=[_trim(g) for g in groups]

    # 19 FAMILY-BALANCE
    fams=[_trim(scores[i:i+3]) for i in range(0,18,3)]
    groups.append(_eight(fams+[_trim(fams),_center(sum(x>0 for x in fams),3,3)]))
    # 20 HALF-CROSS
    h=n//2
    groups.append(_eight([
        _center(_mean(nib[:h])-_mean(nib[h:]),0,5),_auto(nib,max(1,h-1)),
        _center(_entropy(nib[:h])-_entropy(nib[h:]),0,.4),
        _center(_mean([nib[i]^nib[(i+h)%n] for i in range(h)]),7.5,5),
        _center(_mean(nib[:8])-_mean(nib[-8:]),0,5),_auto(nib,4),_auto(nib,8),
        _trim([scores[0],scores[3],scores[14],scores[16]])
    ]))
    # 21 QUARTER-FLOW
    q=max(1,n//4); qs=[nib[i*q:(i+1)*q if i<3 else n] for i in range(4)]; qm=[_mean(x) for x in qs]
    groups.append(_eight([
        _center(qm[3]-qm[0],0,5),_center(qm[2]-qm[1],0,5),
        _center((qm[0]+qm[3])-(qm[1]+qm[2]),0,8),
        _center(max(qm)-min(qm),3.5,3),_auto(qm,1),_trans_bool([x>7.5 for x in qm]),
        _trim(scores[4:11]),_trim(scores[14:18])
    ]))
    # 22 HISTOGRAM-SKEW
    hist=[0]*16
    for v in nib:hist[v]+=1
    groups.append(_eight([
        _center(sum(hist[8:])-sum(hist[:8]),0,n),
        _center(sum(hist[::2])-sum(hist[1::2]),0,n),
        _center(max(hist)/n,1/16,.16),_center(_entropy(nib),.82,.24),
        _center(_mean(hist[:4])-_mean(hist[-4:]),0,n/10),
        _center(hist[0]+hist[15],n/8,n/8),
        _trim(scores[:6]),_trim(scores[10:16])
    ]))
    # 23 LAG-SPECTRAL
    groups.append(_eight([_auto(nib,l) for l in (1,2,3,5,7,9,11,13)]))
    # 24 SEGMENT-STABILITY
    seg=max(4,n//8); ss=[nib[i:i+seg] for i in range(0,n,seg)]
    sm=[_mean(x) for x in ss]; se=[_entropy(x) for x in ss]
    groups.append(_eight([
        _center(max(sm)-min(sm),3.2,3),_center(max(se)-min(se),.25,.3),
        _center(sm[-1]-sm[0],0,5),_center(se[-1]-se[0],0,.4),
        _auto(sm,1),_auto(se,1),_trim(scores[10:17]),_trim(scores[:8])
    ]))
    # 25 ENTROPY-BANDS
    low=sum(v<4 for v in nib)/n; mid=sum(4<=v<12 for v in nib)/n; high=sum(v>=12 for v in nib)/n
    groups.append(_eight([
        _center(_entropy(nib),.82,.24),_center(_entropy(list(raw)),.9,.2),
        _center(low,.25,.25),_center(mid,.5,.3),_center(high,.25,.25),
        _center(high-low,0,.4),_trim(scores[:12]),_trim(scores[12:18])
    ]))
    # 26 DIGEST-CONSENSUS
    ds=scores[6:14]
    groups.append(_eight([
        _trim(ds),_mean(ds),_center(sum(x>0 for x in ds)-sum(x<0 for x in ds),0,5),
        _trim([scores[6],scores[12]]),_trim([scores[7],scores[13]]),
        _trim([scores[8],scores[17]]),_trim(scores[6:9]),_trim(scores[12:18])
    ]))
    # 27 ROBUST-STACK
    pre=[_trim(g) for g in groups]
    med=statistics.median(pre)
    groups.append(_eight([
        _trim(pre),_mean(pre),med,
        _center(sum(x>.02 for x in pre)-sum(x<-.02 for x in pre),0,8),
        _trim(pre[:9]),_trim(pre[9:18]),_trim(pre[18:]),_trim(fams)
    ]))

    # 28 HEX-RUN-PROFILE
    signs=[v>=8 for v in nib]
    runs=[]
    if signs:
        cur=1
        for i in range(1,len(signs)):
            if signs[i]==signs[i-1]:cur+=1
            else:runs.append(cur);cur=1
        runs.append(cur)
    groups.append(_eight([
        _center(_mean(runs),2.0,2.4),
        _center(max(runs) if runs else 0,4.0,4.0),
        _center(len(runs),n/2,max(1,n/2)),
        _trans_bool(signs),
        _center(sum(r>=3 for r in runs),max(1,len(runs))/4,max(1,len(runs))/2),
        _center(sum(r&1 for r in runs)/max(1,len(runs)),.5,.5),
        _auto(runs,1),_auto(runs,2)
    ]))

    # 29 PRIME-POS-FLOW
    prime_idx=[i for i in range(n) if i in (2,3,5,7) or (i>7 and all(i%d for d in range(2,int(i**.5)+1)))]
    nonprime=[i for i in range(n) if i not in set(prime_idx)]
    pv=[nib[i] for i in prime_idx] or nib
    nv=[nib[i] for i in nonprime] or nib
    groups.append(_eight([
        _center(_mean(pv)-_mean(nv),0,4.5),
        _center(_entropy(pv)-_entropy(nv),0,.35),
        _center(sum(v>=8 for v in pv)/len(pv),.5,.5),
        _center(sum(v&1 for v in pv)/len(pv),.5,.5),
        _auto(pv,1),_auto(pv,2),
        _center(sum((i+1)*nib[i] for i in prime_idx)%127,63,63),
        _center(sum(nib[i] for i in prime_idx)%61,30,30)
    ]))

    # 30 BITPLANE-SPECTRUM
    bitplanes=[[((v>>bit)&1) for v in nib] for bit in range(4)]
    groups.append(_eight([
        _center(_mean(bitplanes[0]),.5,.5),_center(_mean(bitplanes[1]),.5,.5),
        _center(_mean(bitplanes[2]),.5,.5),_center(_mean(bitplanes[3]),.5,.5),
        _trans_bool(bitplanes[0]),_trans_bool(bitplanes[1]),
        _trim([_auto(bp,1) for bp in bitplanes]),
        _trim([_auto(bp,2) for bp in bitplanes])
    ]))

    # 31 CROSS-DIGEST-CORR
    dsha=list(_digest_bytes('sha256',raw))
    dsha3=list(_digest_bytes('sha3',raw))
    dblake=list(_digest_bytes('blake2',raw))
    dmd5=list(_digest_bytes('md5',raw))
    def _pair_corr(a,b):
        m=min(len(a),len(b))
        if m<2:return 0.0
        aa=a[:m];bb=b[:m];ma=_mean(aa);mb=_mean(bb)
        num=sum((x-ma)*(y-mb) for x,y in zip(aa,bb))
        da=math.sqrt(sum((x-ma)**2 for x in aa));db=math.sqrt(sum((y-mb)**2 for y in bb))
        return _clamp(num/(da*db)) if da and db else 0.0
    groups.append(_eight([
        _pair_corr(dsha,dsha3),_pair_corr(dsha,dblake),_pair_corr(dsha3,dblake),
        _pair_corr(dsha,dmd5),_pair_corr(dsha3,dmd5),_pair_corr(dblake,dmd5),
        _center(_mean(dsha)-_mean(dsha3),0,60),
        _center(_mean(dblake)-_mean(dmd5),0,60)
    ]))

    # 32 MULTISCALE-BLOCK
    mvals=[]
    for block in (2,4,8,16):
        if block>n: mvals.extend([0.0,0.0]); continue
        bs2=[nib[i:i+block] for i in range(0,n,block)]
        means=[_mean(x) for x in bs2 if x]
        mvals.extend([
            _center((max(means)-min(means)) if means else 0,3.5,3.5),
            _auto(means,1)
        ])
    groups.append(_eight(mvals))

    # 33 PERMUTATION-VOTE
    perms=[]
    idx=list(range(n))
    orders=[
        idx,
        list(reversed(idx)),
        idx[::2]+idx[1::2],
        idx[1::2]+idx[::2],
        sorted(idx,key=lambda i:(i%4,i)),
        sorted(idx,key=lambda i:(i%3,i)),
        sorted(idx,key=lambda i:((i*5)%n)),
        sorted(idx,key=lambda i:((i*7)%n)),
    ]
    for order in orders:
        seq=[nib[i] for i in order]
        perms.append(_trim([
            _center(_mean(seq[:max(1,n//3)])-_mean(seq[-max(1,n//3):]),0,4.5),
            _auto(seq,1),_auto(seq,2),
            _center(sum((j+1)*v for j,v in enumerate(seq))%(16*n),8*n,8*n)
        ]))
    groups.append(_eight(perms))

    # 34 RESIDUE-ENSEMBLE
    residues=[]
    intval=int(z,16)
    for mod in (17,29,31,43,61,73,97,127):
        residues.append(_center(intval%mod,(mod-1)/2,max(1,(mod-1)/2)))
    groups.append(_eight(residues))

    # 35 PERTURB-STABILITY
    # deterministic small transforms; measures whether structural vote keeps direction.
    pert=[]
    seqs=[
        nib[1:]+nib[:1],
        nib[3:]+nib[:3],
        list(reversed(nib)),
        [v^0xF for v in nib],
        [nib[i]^nib[-1-i] for i in range(n)],
        nib[::2]+nib[1::2],
        nib[1::2]+nib[::2],
        [((v<<1)&0xF)|(v>>3) for v in nib],
    ]
    for seq in seqs:
        pert.append(_trim([
            _center(_mean(seq),7.5,5),
            _auto(seq,1),_auto(seq,2),
            _center(sum(v>=8 for v in seq)/len(seq),.5,.5),
            _center(_entropy(seq),.82,.24)
        ]))
    groups.append(_eight(pert))

    # 36 META-CONSENSUS
    pre35=[_trim(g) for g in groups[:35]]
    fam35=[_trim(pre35[i:i+3]) for i in range(0,33,3)]
    tail35=pre35[33:35]
    groups.append(_eight([
        _trim(pre35),_mean(pre35),statistics.median(pre35),
        _trim(fam35),_mean(fam35),
        _center(sum(x>.015 for x in pre35)-sum(x<-.015 for x in pre35),0,10),
        _trim(tail35),_trim(pre35[-9:])
    ]))

    module_scores=[_trim(g) for g in groups[:36]]

    # 12 equal families x 3 modules: correlated variants cannot dominate just by count.
    families=[_trim(module_scores[i:i+3]) for i in range(0,36,3)]
    family_core=_trim(families)
    global_core=_trim(module_scores)
    median_core=statistics.median(module_scores)
    raw=.60*family_core+.25*global_core+.15*median_core

    # Perturbation direction is used only as a small stability term.
    perturb_score=module_scores[34]
    meta_score=module_scores[35]
    raw += _clamp(perturb_score,-1,1)*.010 + _clamp(meta_score,-1,1)*.008

    # Neutral-center calibration for uniformly distributed cryptographic hashes.
    # This removes a structural positive offset from the feature families so
    # the engine itself does not systematically prefer TÀI or XỈU.
    raw -= .035

    # Deterministic tie-break, never random.
    if abs(raw)<.0028:
        tie=hashlib.sha256(('SECURE288:'+kind+':'+z).encode()).digest()[0]
        raw=.0030 if tie&1 else -.0030

    prediction='TÀI' if raw>0 else 'XỈU'
    fam_pos=sum(x>.004 for x in families); fam_neg=sum(x<-.004 for x in families)
    active=fam_pos+fam_neg
    agreement=(max(fam_pos,fam_neg)/active) if active else .5

    # Stability blends family agreement + perturb/meta consistency.
    perturb_consistency=.5+.5*min(1.0,abs(perturb_score))
    meta_consistency=.5+.5*min(1.0,abs(meta_score))
    stability=.62*agreement+.23*perturb_consistency+.15*meta_consistency

    # "strength" is a signal-strength indicator, not a win probability.
    strength=max(50.1,min(59.4,
        50 + abs(raw)*17.0 + max(0,stability-.5)*7.0
    ))
    level='MẠNH' if strength>=57.2 and stability>=.68 else 'VỪA' if strength>=54.1 and stability>=.59 else 'NHẸ'

    rows=sorted(
        [{'name':MODULE_NAMES[i],'score':round(module_scores[i],6),'prediction':'TÀI' if module_scores[i]>0 else 'XỈU'}
         for i in range(36)],
        key=lambda x:abs(x['score']), reverse=True
    )
    return {
        'ok':True,'kind':kind,'prediction':prediction,'strength':round(strength,2),
        'agreement':round(agreement*100,1),'stability':round(stability*100,1),'level':level,
        'family_tai':sum(x>0 for x in families),'family_xiu':sum(x<=0 for x in families),
        'module_tai':sum(x>0 for x in module_scores),'module_xiu':sum(x<=0 for x in module_scores),
        'module_count':36,'signal_count':288,'engine':'SECURE-288',
        'top':rows[:8]
    }
