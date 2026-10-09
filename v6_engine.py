"""V6 causal, versioned expert layer.

Every prediction is a historical hypothesis, NOT an actionable claim about
fair random dice or cards. Live performance must be audited separately from
replay. No future rounds or settlement results are used during inference.
"""
from collections import deque
from math import log2

T, X = 'TÀI', 'XỈU'
VERSION = 'V6_'


def flip(side):
    return X if side == T else T


def choose(t, x):
    return T if t > x else X if x > t else None


def beta_rate(t, x, prior=3.0):
    return (t + prior) / (t + x + 2 * prior)


def _context(seq, k, min_support=8, max_lookback=320):
    a = seq[-max_lookback:]
    if len(a) < k + min_support:
        return None
    suffix = a[-k:]
    tt = xx = 0
    for i in range(k, len(a)):
        if a[i-k:i] == suffix:
            tt += a[i] == T
            xx += a[i] == X
    n = tt + xx
    if n < min_support:
        return None
    p = beta_rate(tt, xx)
    # A tiny difference is not a statistically meaningful signal.
    return choose(tt, xx) if abs(p - .5) >= .065 else None


def _runlength(seq, min_support=8):
    if len(seq) < 25:
        return None
    # Historical state: exact previous side and capped current run length.
    current = seq[-1]
    span = 1
    for s in reversed(seq[:-1]):
        if s == current: span += 1
        else: break
    bucket = min(span, 5)
    tt = xx = 0
    for j in range(1, len(seq)):
        p = seq[j-1]
        run = 1
        for z in range(j-2, -1, -1):
            if seq[z] == p: run += 1
            else: break
        if p == current and min(run,5) == bucket:
            tt += seq[j] == T
            xx += seq[j] == X
    return choose(tt, xx) if tt + xx >= min_support and abs(beta_rate(tt,xx)-.5) >= .065 else None


def _pattern(seq, maxlen=8, support=6):
    if len(seq) < maxlen + support + 5:
        return None
    best = (0, None)
    for k in range(3, maxlen+1):
        t = x = 0
        pat = seq[-k:]
        for j in range(k, len(seq)):
            if seq[j-k:j] == pat:
                t += seq[j] == T
                x += seq[j] == X
        n = t + x
        if n >= support:
            edge = abs(beta_rate(t,x)-.5)
            quality = edge * min(1., n/16) / (1 + .03 * k)
            if edge >= .085 and quality > best[0]:
                best = quality, choose(t,x)
    return best[1]


def _run_shape(seq):
    if len(seq) < 10:
        return None
    runs = []
    for s in seq:
        if runs and runs[-1][0] == s:
            runs[-1][1] += 1
        else:
            runs.append([s,1])
    if len(runs) < 5:
        return None
    lengths = [r[1] for r in runs]
    # The final run may be unfinished. Avoid claiming a turn solely because
    # the last run length resembles a completed historic template.
    for unit in ((1,1),(2,2),(1,2),(2,1),(2,3),(3,2),(3,3)):
        if len(lengths) < 5:
            continue
        completed = lengths[-5:-1]
        if completed != list(unit)*2:
            continue
        expected = unit[0]
        return seq[-1] if lengths[-1] < expected else flip(seq[-1])
    return None


def _period(seq):
    if len(seq) < 20: return None
    best = (0., None)
    for lag in range(2, 11):
        n = min(35,len(seq)-lag)
        if n < 12: continue
        match = sum(seq[-i]==seq[-i-lag] for i in range(1,n+1))
        p=(match+3)/(n+6)
        if p > best[0]: best=(p, seq[-lag])
    return best[1] if best[0] >= .75 else None


def _dice(seq, metas, k=0):
    if not metas or len(seq)!=len(metas) or len(seq)<30:
        return None
    def band(meta):
        try:
            n = int((meta or {}).get('total'))
            if n < 3 or n >18: return None
            return (n <= 7) if k==0 else (n>=14) if k==1 else (n-3)//4
        except (ValueError,TypeError,AttributeError):return None
    state=band(metas[-1]);t=x=0
    if state is None:return None
    for i in range(1,len(seq)):
        if band(metas[i-1])==state:
            t+=seq[i]==T;x+=seq[i]==X
    return choose(t,x) if t+x>=12 and abs(beta_rate(t,x)-.5)>=.075 else None


def _bcr(seq):
    # Only a descriptive historic road hypothesis. Ties skipped by upstream.
    if len(seq)<12:return None
    windows=seq[-10:]
    transition=sum(a!=b for a,b in zip(windows, windows[1:])) / 9
    if transition >= .83:return flip(seq[-1])
    if transition <= .23:return seq[-1]
    return None


def strategies(seq, board='sunwin:hu', meta_history=None, legacy=None):
    a=[x for x in seq if x in (T,X)]
    if not a:return {}
    last=a[-1]
    vals={
        'FOLLOW': last,
        'REVERSE': flip(last),
        'MARKOV1': _context(a,1,8),
        'MARKOV2': _context(a,2,8),
        'MARKOV3': _context(a,3,6),
        'MARKOV4': _context(a,4,6),
        'SUFFIX': _pattern(a),
        'RUN_HAZARD': _runlength(a),
        'RUN_SHAPE': _run_shape(a),
        'CYCLE': _period(a),
        'BIAS_MOMENTUM': (T if a[-24:].count(T)/len(a[-24:])>=.67 else X if a[-24:].count(T)/len(a[-24:])<=.33 else None) if len(a)>=20 else None,
        'BIAS_REVERT': (X if a[-30:].count(T)/len(a[-30:])>=.77 else T if a[-30:].count(T)/len(a[-30:])<=.23 else None) if len(a)>=25 else None,
    }
    if str(board).startswith('sunwin:'):
        vals['DICE_BAND']=_dice(a,meta_history,0)
        vals['DICE_EXTREMES']=_dice(a,meta_history,1)
        vals['DICE_BUCKETS']=_dice(a,meta_history,2)
    if str(board).startswith('baccarat:'):
        vals['BCR_ROAD']=_bcr(a)
    # Classic legacy is available for diagnostic only, never the default winner.
    # It has been heavily one-sided in the user's historical report.
    return {VERSION+key:val for key,val in vals.items() if val in (T,X)}


def append_result(logs, forecasts, actual):
    for name, predicted in forecasts.items():
        logs.setdefault(name,deque(maxlen=100)).append({
            'correct': int(predicted == actual), 'actual': actual,
            'prediction': predicted
        })


def _normalize(entries):
    # Accept historic boolean lists from V5 and V6 structured logs.
    out=[]
    for item in list(entries)[-100:]:
        if isinstance(item,dict):
            actual=item.get('actual');pred=item.get('prediction')
            if actual in (T,X) and pred in (T,X):
                out.append((int(actual==pred),actual,pred))
        else:
            out.append((int(bool(item)),None,None))
    return out


def _rate(items):
    n=len(items)
    return (sum(z[0] for z in items)+12)/(n+24) if n else .5


def _candidate(entries):
    data=_normalize(entries)
    n=len(data)
    if n<45:return None
    slices=(data[-20:],data[-50:],data[-100:])
    s=.43*_rate(slices[0])+.37*_rate(slices[1])+.20*_rate(slices[2])
    # Compare fixed-side baselines with the expert over IDENTICAL time
    # windows: this prevents a lucky TÀI streak from looking like model skill.
    labeled=[z for z in data[-100:] if z[1] in (T,X)]
    baseline=.5
    if len(labeled)>=30:
        vals=[]
        for window in slices:
            avail=[z for z in window if z[1] in (T,X)]
            t=sum(z[1]==T for z in avail)
            xx=len(avail)-t
            vals.append(max((t+12)/(len(avail)+24), (xx+12)/(len(avail)+24)))
        baseline=.43*vals[0]+.37*vals[1]+.20*vals[2]
    labels=[z[2] for z in labeled]
    biased=(max(labels.count(T),labels.count(X))/len(labels) > .82) if len(labels)>=30 else False
    if biased:s-=.022
    if len(data)>=4 and not any(z[0] for z in data[-4:]):s-=.023
    # Positive matched edge + modest margin required; no automatic champion.
    return (s, baseline, n) if s > max(.516,baseline+.025) else None


def fallback(hist):
    import hashlib
    a=[v for v in hist if v in (T,X)]
    if len(a)>=40:
        prediction=_context(a,1,14)
        if prediction is not None:
            return prediction, 'MARKOV THỬ NGHIỆM'
        prediction=_context(a,2,12)
        if prediction is not None:
            return prediction, 'MARKOV BẬC 2'
    # Deterministic tie-break, intentionally no predictive claim.
    key=''.join('T' if v==T else 'X' for v in a[-64:]).encode()
    bit=hashlib.blake2b(key,digest_size=1,person=b'CAU-V6').digest()[0] & 1
    return (T if bit else X), 'KHÔNG CÓ LỢI THẾ KIỂM CHỨNG'


def select(predictions, logs, current_champion=None, history=None):
    options=[]
    for name in predictions:
        if not name.startswith(VERSION):continue
        stats=_candidate(logs.get(name,()))
        if stats is not None:
            score,baseline,n=stats
            options.append((score,name,baseline,n))
    options.sort(reverse=True)
    chosen=options[0] if options else None
    old=next((r for r in options if r[1]==current_champion),None)
    # Do not switch because of one lucky result.
    if chosen and old and chosen[1]!=current_champion and chosen[0]-old[0]<.055:
        chosen=old
    if chosen:
        score,name,base,n=chosen
        return {'prediction':predictions[name], 'champion':name,
                'mode':'V6 · HỌC CẦU KIỂM CHỨNG', 'sample_count':n,
                'historical_score':round(score,4),
                'baseline_score':round(base,4),
                'top':[{'name':r[1], 'score':round(r[0],4), 'n':r[3]} for r in options[:5]]}
    pred,reason=fallback(history or [])
    return {'prediction':pred, 'champion':None, 'mode':reason,
            'sample_count':len(history or []), 'historical_score':.5,
            'baseline_score':.5, 'top':[]}
