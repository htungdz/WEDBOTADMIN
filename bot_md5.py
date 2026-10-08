# DEVELOPER THANHTUNG VIP · MD5 + SHA256 ULTRA TELEGRAM ANALYZER
# Dual hash · ULTRA-144 deterministic ensemble · debiased · online calibration + signature memory
# Run: python bot_md5.py

import os
import re
import math
import time
import asyncio
import hashlib
import zlib
import sqlite3
from collections import OrderedDict

import httpx

BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
ADMIN_IDS = {int(x) for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip().lstrip('-').isdigit()}
BOT_POLL_TIMEOUT = max(5, int(os.getenv('BOT_POLL_TIMEOUT', '20')))
BOT_NAME = 'DEVELOPER THANHTUNG VIP'
DB_PATH = os.getenv('DB_PATH', 'md5_sha256_max.db').strip() or 'md5_sha256_max.db'

MD5_RE = re.compile(r'^[0-9a-fA-F]{32}$')
SHA256_RE = re.compile(r'^[0-9a-fA-F]{64}$')
HASH_TOKEN_RE = re.compile(r'(?<![0-9a-fA-F])([0-9a-fA-F]{64}|[0-9a-fA-F]{32})(?![0-9a-fA-F])')
CACHE_MAX = 20000
_CACHE = OrderedDict()
_STATS = {'started': time.time(), 'total': 0, 'md5': 0, 'sha256': 0, 'private': 0, 'group': 0}
SEM = asyncio.Semaphore(64)

MODULE_NAMES = (
    'NIBBLE-DIST', 'BYTE-DIST', 'PARITY-FLOW', 'SYMMETRY',
    'POSITIONAL', 'MOD-FOLD', 'SHA256-MIX', 'SHA3-MIX',
    'BLAKE2-MIX', 'ROTATION', 'CHUNK-VOTE', 'CHECKSUM',
    'SHA512-MIX', 'MD5-MIX', 'MIRROR-XOR', 'HAMMING-FLOW',
    'WINDOW-FLOW', 'AVALANCHE-MIX'
)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def centered(v, mid, scale):
    if not scale:
        return 0.0
    return clamp((float(v) - float(mid)) / float(scale), -1.0, 1.0)


def entropy_values(values):
    if not values:
        return 0.0
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    n = len(values)
    e = 0.0
    for c in counts.values():
        p = c / n
        e -= p * math.log2(p)
    return e


def autocorr(xs, lag):
    if len(xs) <= lag + 1:
        return 0.0
    mean = sum(xs) / len(xs)
    den = sum((x - mean) ** 2 for x in xs) or 1.0
    num = sum((xs[i] - mean) * (xs[i-lag] - mean) for i in range(lag, len(xs)))
    return clamp(num / den, -1.0, 1.0)


def transition_score(bits):
    if len(bits) < 2:
        return 0.0
    changes = sum(1 for a, b in zip(bits, bits[1:]) if a != b)
    return centered(changes / (len(bits) - 1), 0.5, 0.5)


def chunks(seq, n=4):
    L = len(seq)
    out = []
    for i in range(n):
        a = round(i * L / n)
        b = round((i + 1) * L / n)
        out.append(seq[a:b])
    return out


def trim_mean(vals):
    if not vals:
        return 0.0
    s = sorted(vals)
    if len(s) >= 6:
        s = s[1:-1]
    return sum(s) / len(s)


def digest_signals(d):
    vals = list(d)
    bits = [(b >> k) & 1 for b in vals for k in range(7, -1, -1)]
    out = []
    for part in chunks(vals, 4):
        out.append(centered(sum(part) / max(1, len(part)), 127.5, 78.0))
    out.append(centered(sum(bits) / max(1, len(bits)), 0.5, 0.22))
    out.append(autocorr(vals, 1))
    out.append(autocorr(vals, 3))
    out.append(transition_score([b >= 128 for b in vals]))
    return [clamp(x, -1.0, 1.0) for x in out[:8]]


def rotate_list(a, k):
    if not a:
        return a
    k %= len(a)
    return a[k:] + a[:k]


def build_max96(z):
    """Return 12 independent-ish module scores built from 96 deterministic signals."""
    z = z.lower()
    nib = [int(c, 16) for c in z]
    bs = list(bytes.fromhex(z))
    bits = [(b >> k) & 1 for b in bs for k in range(7, -1, -1)]
    N = len(nib)
    B = len(bs)
    groups = []

    # 1) nibble distribution
    g = []
    for p in chunks(nib, 4):
        g.append(centered(sum(p) / max(1, len(p)), 7.5, 4.6))
    for p in chunks(nib, 4):
        g.append(centered(sum(x >= 8 for x in p) / max(1, len(p)), .5, .42))
    groups.append(g)

    # 2) byte distribution
    g = []
    for p in chunks(bs, 4):
        g.append(centered(sum(p) / max(1, len(p)), 127.5, 78.0))
    for p in chunks(bs, 4):
        g.append(centered(sum((x & 1) == 0 for x in p) / max(1, len(p)), .5, .42))
    groups.append(g)

    # 3) parity / flow
    g = [
        transition_score([x >= 8 for x in nib]),
        transition_score([x & 1 for x in nib]),
        transition_score(bits),
        centered(sum(bits) / len(bits), .5, .22),
        centered(sum((x & 1) == 0 for x in nib) / N, .5, .42),
        centered(sum(x in (0, 15) for x in nib) / N, .125, .16),
        autocorr(nib, 1),
        autocorr(nib, 2),
    ]
    groups.append(g)

    # 4) symmetry / entropy
    rev = nib[::-1]
    half = N // 2
    g = [
        centered((sum(nib[:half]) / half) - (sum(nib[half:]) / (N-half)), 0, 4.8),
        centered(sum(abs(a-b) for a, b in zip(nib, rev)) / N, 5.3, 3.0),
        centered(len(set(nib)), 12.0 if N == 32 else 15.0, 4.0),
        centered(entropy_values(nib), 3.72 if N == 32 else 3.86, .34),
        autocorr(nib, 3),
        autocorr(nib, 5),
        centered(sum(nib[::2]) / len(nib[::2]), 7.5, 4.6),
        centered(sum(nib[1::2]) / len(nib[1::2]), 7.5, 4.6),
    ]
    groups.append(g)

    # 5) positional / indexed
    idx_a = [i for i in range(N) if i % 3 == 0]
    idx_b = [i for i in range(N) if i % 3 == 1]
    idx_c = [i for i in range(N) if i % 3 == 2]
    primes = [i for i in range(2, N) if all(i % d for d in range(2, int(i**.5)+1))]
    fib = [i for i in (0,1,2,3,5,8,13,21,34,55) if i < N]
    g = [
        centered(sum(nib[i] for i in idx_a)/len(idx_a), 7.5, 4.6),
        centered(sum(nib[i] for i in idx_b)/len(idx_b), 7.5, 4.6),
        centered(sum(nib[i] for i in idx_c)/len(idx_c), 7.5, 4.6),
        centered(sum(nib[i] for i in primes)/max(1,len(primes)), 7.5, 4.6),
        centered(sum(nib[i] for i in fib)/max(1,len(fib)), 7.5, 4.6),
        centered(sum(nib[i] for i in range(0,N,4))/len(range(0,N,4)), 7.5, 4.6),
        centered(sum(nib[i] for i in range(1,N,4))/len(range(1,N,4)), 7.5, 4.6),
        centered(sum((i+1)*nib[i] for i in range(N)) % 257, 128, 128),
    ]
    groups.append(g)

    # 6) modular folds
    xorb = 0
    for b in bs:
        xorb ^= b
    pairxor = [nib[i] ^ nib[(i+1) % N] for i in range(0, N, 2)]
    g = [
        centered(sum(nib) % 17, 8, 8),
        centered(xorb % 17, 8, 8),
        centered(int(z[:min(16,N)], 16) % 97, 48, 48),
        centered(int(z[-min(16,N):], 16) % 97, 48, 48),
        centered(sum(pairxor)/max(1,len(pairxor)), 7.5, 4.6),
        centered(sum((nib[i] ^ nib[(i+7)%N]) for i in range(N))/N, 7.5, 4.6),
        centered(sum((nib[i] + nib[(i+11)%N]) % 16 for i in range(N))/N, 7.5, 4.6),
        centered(sum((nib[i] - nib[(i+5)%N]) % 16 for i in range(N))/N, 7.5, 4.6),
    ]
    groups.append(g)

    # 7-9) derived digest families
    groups.append(digest_signals(hashlib.sha256(z.encode()).digest()))
    groups.append(digest_signals(hashlib.sha3_256(z.encode()).digest()))
    groups.append(digest_signals(hashlib.blake2s(z.encode()).digest()))

    # 10) rotations / circular relations
    r3, r7, r13 = rotate_list(nib, 3), rotate_list(nib, 7), rotate_list(nib, 13)
    g = [
        centered(sum(abs(a-b) for a,b in zip(nib,r3))/N, 5.3, 3.0),
        centered(sum(abs(a-b) for a,b in zip(nib,r7))/N, 5.3, 3.0),
        centered(sum(abs(a-b) for a,b in zip(nib,r13))/N, 5.3, 3.0),
        centered(sum((a^b) for a,b in zip(nib,r3))/N, 7.5, 4.6),
        centered(sum((a^b) for a,b in zip(nib,r7))/N, 7.5, 4.6),
        centered(sum((a^b) for a,b in zip(nib,r13))/N, 7.5, 4.6),
        autocorr(nib, 7),
        autocorr(nib, 11 if N > 32 else 9),
    ]
    groups.append(g)

    # 11) chunk consensus: contrast each chunk with global center
    g = []
    nib_chunks = chunks(nib, 8)
    for p in nib_chunks:
        g.append(centered(sum(p)/max(1,len(p)), 7.5, 4.6))
    groups.append(g)

    # 12) checksums / independent folds
    crc = zlib.crc32(z.encode()) & 0xffffffff
    ad = zlib.adler32(z.encode()) & 0xffffffff
    d1 = hashlib.blake2b(z.encode(), digest_size=8).digest()
    d2 = hashlib.sha512(z.encode()).digest()[:8]
    g = [
        centered(crc % 257, 128, 128),
        centered(ad % 257, 128, 128),
        centered(int.from_bytes(d1[:2],'big') % 257, 128, 128),
        centered(int.from_bytes(d1[2:4],'big') % 257, 128, 128),
        centered(int.from_bytes(d2[:2],'big') % 257, 128, 128),
        centered(int.from_bytes(d2[2:4],'big') % 257, 128, 128),
        centered(sum(bs[::2])/max(1,len(bs[::2])),127.5,78.0),
        centered(sum(bs[1::2])/max(1,len(bs[1::2])),127.5,78.0),
    ]
    groups.append(g)

    # exact 96 signals, robust module means
    groups = [[clamp(float(v), -1.0, 1.0) for v in g[:8]] for g in groups[:12]]
    module_scores = [trim_mean(g) for g in groups]
    return groups, module_scores



# Preserve the ULTRA-144 core and add 48 extra deterministic signals (6x8).
_build_max96_core = build_max96

def _bit_hamming(a,b):
    return (a^b).bit_count()

def build_max96(z):
    groups, _ = _build_max96_core(z)
    z=z.lower(); nib=[int(c,16) for c in z]; bs=list(bytes.fromhex(z)); N=len(nib); B=len(bs)

    # 13) SHA512 derived mix
    groups.append(digest_signals(hashlib.sha512(z.encode()).digest()[:32]))
    # 14) MD5 derived mix, expanded deterministically to 32 bytes
    md=hashlib.md5(z.encode()).digest(); groups.append(digest_signals(md+hashlib.md5(md).digest()))

    # 15) mirror xor / distance
    rev=bs[::-1]
    g=[
        centered(sum((a^b) for a,b in zip(bs,rev))/max(1,B),127.5,78.0),
        centered(sum(abs(a-b) for a,b in zip(bs,rev))/max(1,B),85.0,55.0),
        centered(sum(_bit_hamming(a,b) for a,b in zip(bs,rev))/max(1,B),4.0,3.0),
        autocorr(bs,2), autocorr(bs,5),
        transition_score([a>b for a,b in zip(bs,rev)]),
        centered(sum((a+b)&255 for a,b in zip(bs,rev))/max(1,B),127.5,78.0),
        centered(sum((a-b)&255 for a,b in zip(bs,rev))/max(1,B),127.5,78.0),
    ]; groups.append(g)

    # 16) hamming / bit flow
    g=[]
    for lag in (1,2,3,5):
        pairs=[_bit_hamming(bs[i],bs[i-lag]) for i in range(lag,B)]
        g.append(centered(sum(pairs)/max(1,len(pairs)),4.0,3.0))
    bits=[(b>>k)&1 for b in bs for k in range(8)]
    g += [autocorr(bits,1),autocorr(bits,7),transition_score(bits),centered(sum(bits)/max(1,len(bits)),.5,.22)]
    groups.append(g)

    # 17) local rolling-window flow
    g=[]
    for w in (3,4,5,7,8,11,13,16):
        if N<w: g.append(0.0); continue
        av=[sum(nib[i:i+w])/w for i in range(N-w+1)]
        drift=av[-1]-sum(av)/len(av)
        g.append(centered(drift,0,3.8))
    groups.append(g)

    # 18) avalanche-style transformed digest
    flipped=[]
    for i in range(min(8,len(z))):
        c=int(z[i],16)^1
        zz=hex(c)[2:]+z[1:] if i==0 else z[:i]+hex(c)[2:]+z[i+1:]
        d=hashlib.blake2s(zz.encode()).digest()
        base=hashlib.blake2s(z.encode()).digest()
        flipped.append(sum(_bit_hamming(a,b) for a,b in zip(d,base))/(len(d)*8))
    while len(flipped)<8: flipped.append(.5)
    groups.append([centered(v,.5,.28) for v in flipped[:8]])

    groups=[[clamp(float(v),-1.0,1.0) for v in g[:8]] for g in groups[:18]]
    return groups,[trim_mean(g) for g in groups]

def detect_kind(z):
    if MD5_RE.fullmatch(z):
        return 'MD5'
    if SHA256_RE.fullmatch(z):
        return 'SHA256'
    return None


def db_conn():
    parent = os.path.dirname(os.path.abspath(DB_PATH))
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception:
            pass
    con = sqlite3.connect(DB_PATH, timeout=5)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA synchronous=NORMAL')
    con.execute('''CREATE TABLE IF NOT EXISTS labels(
        hash TEXT PRIMARY KEY, kind TEXT NOT NULL, actual TEXT NOT NULL, created_at INTEGER NOT NULL
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS model_stats(
        kind TEXT NOT NULL, module TEXT NOT NULL,
        tp INTEGER NOT NULL DEFAULT 0, tn INTEGER NOT NULL DEFAULT 0,
        fp INTEGER NOT NULL DEFAULT 0, fn INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(kind,module)
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS signature_stats(
        kind TEXT NOT NULL, signature TEXT NOT NULL,
        tai_count INTEGER NOT NULL DEFAULT 0, xiu_count INTEGER NOT NULL DEFAULT 0,
        samples INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(kind,signature)
    )''')
    return con


def module_weights(kind):
    out = {m: (1.0, 0, .5) for m in MODULE_NAMES}
    try:
        with db_conn() as con:
            rows = con.execute('SELECT module,tp,tn,fp,fn FROM model_stats WHERE kind=?', (kind,)).fetchall()
        for module,tp,tn,fp,fn in rows:
            total = tp+tn+fp+fn
            tpr = (tp+2)/(tp+fn+4)
            tnr = (tn+2)/(tn+fp+4)
            bacc = (tpr+tnr)/2
            # stay conservative until enough real labels exist
            maturity = min(1.0, total/80.0)
            weight = 1.0 + clamp((bacc-.5)*1.4*maturity, -.22, .22)
            out[module] = (weight, total, bacc)
    except Exception:
        pass
    return out


def learned_sample_count(kind):
    try:
        with db_conn() as con:
            return int(con.execute('SELECT COUNT(*) FROM labels WHERE kind=?',(kind,)).fetchone()[0])
    except Exception:
        return 0



def module_signature(scores):
    # Coarse 8-module sign signature = max 256 bins, allowing memory to mature.
    use=scores[:8]
    return ''.join('T' if x>=0 else 'X' for x in use)

def signature_memory(kind,scores):
    sig=module_signature(scores)
    try:
        with db_conn() as con:
            r=con.execute('SELECT tai_count,xiu_count,samples FROM signature_stats WHERE kind=? AND signature=?',(kind,sig)).fetchone()
        if not r: return sig,0,.5
        t,x,n=map(int,r); p=(t+3)/(n+6)
        return sig,n,p
    except Exception:
        return sig,0,.5

def recent_kind_bias(kind,limit=160):
    try:
        with db_conn() as con:
            rows=con.execute('SELECT actual FROM labels WHERE kind=? ORDER BY created_at DESC LIMIT ?',(kind,int(limit))).fetchall()
        n=len(rows)
        if not n: return n,.5
        t=sum(1 for r in rows if r[0]=='TÀI')
        return n,(t+6)/(n+12)
    except Exception:
        return 0,.5

def analyze_hash(z):
    z = z.lower()
    kind = detect_kind(z)
    if not kind:
        raise ValueError('Hash không hợp lệ')
    key = f'{kind}:{z}'
    hit = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)
        return dict(hit)

    groups, scores = build_max96(z)
    weights = module_weights(kind)
    weighted = []
    module_rows = []
    for name, score in zip(MODULE_NAMES, scores):
        w, n, bacc = weights.get(name, (1.0,0,.5))
        ws = score * w
        weighted.append(ws)
        module_rows.append({
            'name': name,
            'score': score,
            'weighted': ws,
            'pred': 'TÀI' if score > 0 else 'XỈU',
            'samples': n,
            'bacc': bacc,
            'weight': w,
        })

    # Robust module ensemble: trim strongest opposite outliers.
    raw = trim_mean(weighted)
    sig,sig_n,sig_p = signature_memory(kind,scores)
    bias_n,bias_p = recent_kind_bias(kind)
    # Learned memory stays weak and evidence-gated so it cannot lock to one side.
    if sig_n >= 6:
        raw += clamp((sig_p-.5)*.055*min(1.0,sig_n/36.0),-.018,.018)
    if bias_n >= 24:
        raw += clamp((bias_p-.5)*.020*min(1.0,bias_n/120.0),-.008,.008)
    pos = sum(1 for s in weighted if s > .012)
    neg = sum(1 for s in weighted if s < -.012)
    active = pos + neg
    agreement = max(pos,neg)/active if active else .5

    # Dead-zone breaker is deterministic and approximately balanced.
    if abs(raw) < .0045:
        bit = hashlib.blake2b((kind+':'+z).encode(), digest_size=1).digest()[0] & 1
        raw = .0048 if bit else -.0048

    pred = 'TÀI' if raw > 0 else 'XỈU'

    # Signal score only. It is intentionally not advertised as a true win probability.
    learned_n = learned_sample_count(kind)
    maturity = min(1.0, learned_n/120.0)
    strength = 50 + min(9.4, abs(raw)*17.0 + max(0,agreement-.5)*6.0 + maturity*.8)
    strength = clamp(strength, 50.20, 59.40)
    tai = strength if pred == 'TÀI' else 100-strength
    xiu = 100-tai
    if strength >= 57.6 and agreement >= .66:
        level = 'KHÁ'
    elif strength >= 54.4 and agreement >= .58:
        level = 'VỪA'
    else:
        level = 'NHẸ'

    ranked = sorted(module_rows, key=lambda x: abs(x['weighted']), reverse=True)
    r = {
        'kind': kind,
        'prediction': pred,
        'tai_score': round(tai,2),
        'xiu_score': round(xiu,2),
        'strength': round(strength,2),
        'agreement': round(agreement*100,1),
        'positive': pos,
        'negative': neg,
        'active': active,
        'level': level,
        'signals': 144,
        'modules': len(MODULE_NAMES),
        'raw': raw,
        'learned_n': learned_n,
        'signature': sig,'signature_n':sig_n,'signature_p':round(sig_p,4),
        'bias_n':bias_n,'bias_p':round(bias_p,4),
        'top_modules': ranked[:5],
    }
    _CACHE[key] = dict(r)
    if len(_CACHE) > CACHE_MAX:
        _CACHE.popitem(last=False)
    return r


def settle_hash(z, actual):
    z = z.lower()
    kind = detect_kind(z)
    actual = actual.upper().replace('TÀI','TAI').replace('XỈU','XIU')
    actual = 'TÀI' if actual in ('TAI','T') else 'XỈU' if actual in ('XIU','X') else None
    if not kind or not actual:
        return False, 'Dữ liệu settle không hợp lệ.'
    groups, scores = build_max96(z)
    try:
        with db_conn() as con:
            old = con.execute('SELECT actual FROM labels WHERE hash=?',(z,)).fetchone()
            if old:
                return False, f'Hash này đã học kết quả {old[0]}.'
            con.execute('INSERT INTO labels(hash,kind,actual,created_at) VALUES(?,?,?,?)',(z,kind,actual,int(time.time())))
            sig=module_signature(scores); t=1 if actual=='TÀI' else 0; x=1-t
            con.execute('''INSERT INTO signature_stats(kind,signature,tai_count,xiu_count,samples,updated_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(kind,signature) DO UPDATE SET
                tai_count=tai_count+excluded.tai_count,xiu_count=xiu_count+excluded.xiu_count,
                samples=samples+1,updated_at=excluded.updated_at''',(kind,sig,t,x,1,int(time.time())))
            for name, score in zip(MODULE_NAMES, scores):
                pred = 'TÀI' if score > 0 else 'XỈU'
                tp=tn=fp=fn=0
                if actual == 'TÀI' and pred == 'TÀI': tp=1
                elif actual == 'XỈU' and pred == 'XỈU': tn=1
                elif actual == 'XỈU' and pred == 'TÀI': fp=1
                else: fn=1
                con.execute('''INSERT INTO model_stats(kind,module,tp,tn,fp,fn,updated_at)
                    VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(kind,module) DO UPDATE SET
                    tp=tp+excluded.tp, tn=tn+excluded.tn, fp=fp+excluded.fp, fn=fn+excluded.fn,
                    updated_at=excluded.updated_at''',
                    (kind,name,tp,tn,fp,fn,int(time.time())))
        # invalidate all cache because weights changed
        _CACHE.clear()
        return True, f'Đã học {kind} → {actual}.'
    except Exception as e:
        return False, f'Lỗi DB: {e}'


def extract_hash(text):
    text = (text or '').strip()
    if detect_kind(text):
        return text.lower()
    m = HASH_TOKEN_RE.search(text)
    return m.group(1).lower() if m else None


def format_result(z, r):
    short = f'{z[:10]}…{z[-10:]}'
    top = ' · '.join(f'{m["name"]}:{"T" if m["pred"]=="TÀI" else "X"}' for m in r['top_modules'][:3])
    return (
        f'<b>⚡ {BOT_NAME}</b>\n'
        f'🔐 <b>{r["kind"]} · ULTRA-144</b>\n'
        f'<code>{short}</code>\n'
        f'━━━━━━━━━━━━━━━━━━\n'
        f'🎯 <b>{r["prediction"]} · {r["level"]}</b>\n'
        f'⚖️ Điểm TÀI <b>{r["tai_score"]:.2f}%</b>  •  XỈU <b>{r["xiu_score"]:.2f}%</b>\n'
        f'🧠 Đồng thuận <b>{r["agreement"]:.1f}%</b> · {r["positive"]}T/{r["negative"]}X module\n'
        f'🧩 <code>{top}</code>\n'
        f'🧬 Memory <b>{r["learned_n"]}</b> mẫu · signature <b>{r["signature_n"]}</b>\n'
        f'<i>Điểm nghiêng thống kê, không phải xác suất chắc thắng.</i>'
    )


async def tg(client, method, payload):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/{method}'
    try:
        r = await client.post(url, json=payload)
        j = r.json()
        return j.get('result') if j.get('ok') else None
    except Exception:
        return None


def reply_payload(chat_id, text, msg=None):
    p = {'chat_id':chat_id,'text':text,'parse_mode':'HTML','disable_web_page_preview':True}
    if msg and msg.get('message_id'):
        p['reply_parameters'] = {'message_id':msg['message_id'],'allow_sending_without_reply':True}
    return p


def start_text():
    return (
        f'<b>⚡ {BOT_NAME}</b>\n'
        '━━━━━━━━━━━━━━━━━━\n'
        '<b>MD5 + SHA256 · ULTRA-144</b>\n\n'
        'Gửi trực tiếp hash:\n'
        '• <b>32 ký tự HEX</b> → MD5\n'
        '• <b>64 ký tự HEX</b> → SHA256\n\n'
        'Bot tự nhận loại hash, chạy 144 tín hiệu / 18 module và trả kết quả ngay.\n'
        'Có chống lệch một phía + calibration theo lịch sử thật khi admin settle.\n\n'
        '<i>Hash một chiều không tự chứa thông tin chắc chắn về kết quả ngẫu nhiên; ULTRA-144 chỉ chấm điểm tín hiệu thống kê.</i>'
    )


def model_text():
    lines = ['<b>🧠 MODEL ULTRA-144</b>']
    for kind in ('MD5','SHA256'):
        weights = module_weights(kind)
        n = learned_sample_count(kind)
        ranked = sorted(weights.items(), key=lambda kv: kv[1][2], reverse=True)
        top = ', '.join(f'{name}:{bacc*100:.1f}%/{tot}' for name,(w,tot,bacc) in ranked[:4])
        lines.append(f'\n<b>{kind}</b> · {n} mẫu\n<code>{top or "chưa có dữ liệu"}</code>')
    return '\n'.join(lines)


async def handle_message(client, msg):
    chat = msg.get('chat') or {}
    chat_id = chat.get('id')
    if chat_id is None:
        return
    ctype = chat.get('type','private')
    text = (msg.get('text') or msg.get('caption') or '').strip()
    if not text:
        return
    actor = (msg.get('from') or {}).get('id')

    if text.startswith('/start') or text.startswith('/help'):
        await tg(client,'sendMessage',reply_payload(chat_id,start_text(),msg if ctype!='private' else None)); return

    if text.startswith('/stats') and actor in ADMIN_IDS:
        up = int(time.time()-_STATS['started'])
        out = (f'<b>📊 MD5 + SHA256 ULTRA</b>\n'
               f'Tổng: <b>{_STATS["total"]}</b> · MD5: {_STATS["md5"]} · SHA256: {_STATS["sha256"]}\n'
               f'Private: {_STATS["private"]} · Group: {_STATS["group"]}\n'
               f'Memory MD5: {learned_sample_count("MD5")} · SHA256: {learned_sample_count("SHA256")}\n'
               f'Uptime: {up//3600}h {(up%3600)//60}m')
        await tg(client,'sendMessage',reply_payload(chat_id,out)); return

    if text.startswith('/model') and actor in ADMIN_IDS:
        await tg(client,'sendMessage',reply_payload(chat_id,model_text())); return

    if text.startswith('/settle') and actor in ADMIN_IDS:
        parts = text.split()
        if len(parts) < 3:
            out = '<b>Dùng:</b> <code>/settle HASH tai</code> hoặc <code>/settle HASH xiu</code>'
        else:
            ok, out = settle_hash(parts[1], parts[2])
            out = ('✅ ' if ok else '⚠️ ') + out
        await tg(client,'sendMessage',reply_payload(chat_id,out,msg if ctype!='private' else None)); return

    z = extract_hash(text)
    if not z:
        return
    r = analyze_hash(z)
    _STATS['total'] += 1
    _STATS['md5' if r['kind']=='MD5' else 'sha256'] += 1
    _STATS['group' if ctype!='private' else 'private'] += 1
    await tg(client,'sendMessage',reply_payload(chat_id,format_result(z,r),msg if ctype!='private' else None))


async def dispatch(client, upd):
    async with SEM:
        try:
            if upd.get('message'):
                await handle_message(client, upd['message'])
        except Exception:
            pass


async def main_async():
    if not BOT_TOKEN:
        raise RuntimeError('Thiếu BOT_TOKEN')
    # initialize DB early so deployment errors are visible
    try:
        with db_conn():
            pass
    except Exception as e:
        print('DB warning:', e)
    limits = httpx.Limits(max_connections=80,max_keepalive_connections=50,keepalive_expiry=30)
    timeout = httpx.Timeout(8.0,connect=3.0,pool=2.0)
    async with httpx.AsyncClient(limits=limits,timeout=timeout) as client:
        await tg(client,'deleteWebhook',{'drop_pending_updates':False})
        await tg(client,'setMyName',{'name':BOT_NAME})
        await tg(client,'setMyShortDescription',{'short_description':'⚡ MD5 + SHA256 ULTRA-144 · dual hash · fast analyzer'})
        await tg(client,'setMyDescription',{'description':'MD5 + SHA256 ULTRA-144 analyzer · 12-module ensemble · optional live calibration.'})
        await tg(client,'setMyCommands',{'commands':[
            {'command':'start','description':'Hướng dẫn MD5 + SHA256'},
            {'command':'help','description':'Cách sử dụng'}
        ]})
        print(f'⚡ {BOT_NAME} · MD5 + SHA256 ULTRA-144 started')
        offset = 0
        tasks = set()
        while True:
            try:
                res = await tg(client,'getUpdates',{
                    'offset':offset,'timeout':BOT_POLL_TIMEOUT,'limit':100,
                    'allowed_updates':['message']
                }) or []
                for upd in res:
                    offset = max(offset,int(upd.get('update_id',0))+1)
                    t = asyncio.create_task(dispatch(client,upd)); tasks.add(t); t.add_done_callback(tasks.discard)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(.35)


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
