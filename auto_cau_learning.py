"""Causal pattern recognizer and per-expert online learner for SUNWIN/Baccarat.

Only already-settled rounds enter history. Reported strengths are empirical
sample descriptions, never probabilities that the next dice/card draw is known.
No external dependencies and no network calls.
"""
from collections import deque
from math import log2

T, X = 'TÀI', 'XỈU'


def flip(x):
    return X if x == T else T


def _choose(t, x, fallback):
    return T if t > x else X if x > t else fallback


def _runs(seq):
    out = []
    for s in seq:
        if out and out[-1][0] == s:
            out[-1] = (s, out[-1][1] + 1)
        else:
            out.append((s, 1))
    return out


def detect_cau(seq):
    """Describe confirmed past patterns; does not claim future draws repeat."""
    a = [x for x in seq if x in (T, X)]
    if not a:
        return {'type': 'CHƯA CÓ CẦU', 'run_length': 0, 'entropy': 1., 'clarity': 0.}
    window = a[-20:]
    p = window.count(T)/len(window)
    ent = 0. if p in (0., 1.) else -p*log2(p)-(1-p)*log2(1-p)
    runs = _runs(a[-40:])
    current = runs[-1][1]
    last10 = a[-10:]
    flips = sum(u != v for u, v in zip(last10, last10[1:]))
    tp = 'NHIỄU / KHÔNG RÕ'
    clarity = 0.
    if current >= 4:
        tp = 'BỆT ' + ('TÀI' if a[-1] == T else 'XỈU')
        clarity = min(.94, .53 + .07*(current-3))
    elif len(last10) >= 6 and flips >= len(last10)-2:
        tp = 'ĐẢO 1-1'
        clarity = .72
    elif len(runs) >= 4:
        last4 = [x[1] for x in runs[-4:]]
        if all(x == 2 for x in last4):
            tp = 'NHỊP 2-2';clarity = .7
        elif all(x == 3 for x in last4):
            tp = 'NHỊP 3-3';clarity = .7
        elif last4 in ([1,2,1,2],[2,1,2,1]):
            tp = 'NHỊP 1-2';clarity = .68
        elif last4 in ([2,3,2,3],[3,2,3,2]):
            tp = 'NHỊP 2-3';clarity = .68
    if tp.startswith('NHIỄU') and len(last10) >= 8 and .42 <= ent <= .92:
        tp = 'CẦU HỖN HỢP';clarity=.28
    return {'type':tp, 'run_length':current,
            'entropy':round(ent,4), 'clarity':round(clarity,3)}


def _markov(seq, k):
    if len(seq) < k + 5:
        return None
    target = seq[-k:]
    t = x = 1.5  # symmetric beta smoothing
    for i in range(k, len(seq)):
        if seq[i-k:i] == target:
            if seq[i] == T: t += 1
            else: x += 1
    if t + x < 5:
        return None
    return _choose(t, x, flip(seq[-1]))


def _suffix(seq):
    for k in (6,5,4,3,2):
        if len(seq) < k + 8: continue
        t = x = 1
        target=seq[-k:]
        for i in range(k,len(seq)):
            if seq[i-k:i]==target:
                if seq[i]==T:t+=1
                else:x+=1
        if t+x>=6:return _choose(t,x,seq[-1])
    return None


def _cycle(seq):
    if len(seq)<12: return None
    best=(0.,None)
    for lag in range(2,9):
        comparisons=min(24,len(seq)-lag)
        if comparisons < 8:continue
        match=sum(seq[-i]==seq[-i-lag] for i in range(1,comparisons+1))
        strength=(match+1)/(comparisons+2)
        if strength > best[0]:best=(strength,seq[-lag])
    return best[1] if best[0]>=.7 else None


def _run_template(seq):
    runs=_runs(seq[-45:])
    if len(runs)<4:return None
    lens=[n for _,n in runs]
    for p in (2,3):
        if len(lens)<p*2:return None
        chunk=lens[-p:]
        if lens[-2*p:-p]==chunk and max(chunk)<=8:
            # If the current run hasn't finished, both extending and ending
            # are plausible: defer to transition model, not fabricated certainty.
            if len(chunk)>=2 and chunk[-1] >= chunk[-2]+2:
                return flip(seq[-1])
            return seq[-1]
    return None


def _sun_dice(seq, metas):
    if not metas or len(seq)<20 or len(metas)!=len(seq):return None
    def band(m):
        total=m.get('total') if isinstance(m,dict) else None
        try:
            n=int(total)
            return 'LOW' if n <= 7 else 'MID_LOW' if n <= 10 else 'MID_HIGH' if n <= 13 else 'HIGH' if n <= 18 else None
        except (ValueError,TypeError):return None
    current=band(metas[-1]);t=x=1
    if not current:return None
    for i in range(1,len(seq)):
        if band(metas[i-1])==current:
            if seq[i]==T:t+=1
            else:x+=1
    return _choose(t,x,seq[-1]) if t+x>=10 else None


def _bcr_road(seq):
    # Banker/Player histories encoded as TÀI/XỈU. Ties are excluded upstream.
    if len(seq)<8:return None
    runs=_runs(seq)
    count=sum(x!=y for x,y in zip(seq[-8:],seq[-7:]))
    if count>=6:return flip(seq[-1])
    if runs[-1][1]>=3:return seq[-1]
    return None


def strategy_predictions(seq, board='sunwin:hu', meta_history=None, legacy=None):
    a=[s for s in seq if s in (T,X)]
    if not a: return {}
    last=a[-1]
    run=_runs(a)[-1][1]
    vals={
        'FOLLOW_LAST':last,
        'REVERSE_LAST':flip(last),
        'MARKOV_1':_markov(a,1),
        'MARKOV_2':_markov(a,2),
        'MARKOV_3':_markov(a,3),
        'RUN_FOLLOW':last if run>=2 else None,
        'RUN_BREAK':flip(last) if run>=3 else None,
        'ALTERNATING_1_1':flip(last) if len(a)>=5 and all(a[-i]!=a[-i-1] for i in range(1,5)) else None,
        'RUN_TEMPLATE':_run_template(a),
        'SUFFIX_MATCH':_suffix(a),
        'PERIOD_2_8':_cycle(a),
        'BIAS_MOMENTUM':T if a[-12:].count(T)>len(a[-12:])*.58 else X if a[-12:].count(T)<len(a[-12:])*.42 else None,
        'BIAS_REVERSION':X if a[-20:].count(T)>len(a[-20:])*.62 else T if a[-20:].count(T)<len(a[-20:])*.38 else None,
    }
    if str(board).startswith('sunwin:'):
        vals['SUN_DICE_BAND']=_sun_dice(a,meta_history)
    if str(board).startswith('baccarat:'):
        vals['BCR_ROAD']=_bcr_road(a)
    if legacy in (T,X):vals['CLASSIC_V3']=legacy
    return {k:v for k,v in vals.items() if v in (T,X)}


def fresh_logs():
    return {}


def record_settled(logs, predictions, actual):
    for name,pred in predictions.items():
        logs.setdefault(name,deque(maxlen=100)).append(pred==actual)


def _score(window):
    """Shrunk, chronological observed score, never a future probability.

    Only previously settled rounds can influence the next decision.
    A prior centered at 50% and a sample floor reduce lucky champions.
    """
    n=len(window)
    if n<25:return -1.
    w20=window[-20:];w50=window[-50:];w100=window[-100:]
    def rate(xs):return (sum(xs)+12)/(len(xs)+24)
    value=.40*rate(w20)+.40*rate(w50)+.20*rate(w100)
    if n<45:value-=.03
    if len(window)>=4 and sum(window[-4:])==0:value-=.035
    # Penalize extensive model selection: with many experts, lucky winners
    # overfit historical noise. No strategy has a guaranteed edge.
    return value-.012


def _fallback_prediction(preds, history=None):
    """No CLASSIC-only fallback; neutral if no evidence for a transition.

    Uses only prior outcomes. A deterministic hash tie-break is explicitly
    non-predictive, and removes systematic default-TÀI preference.
    """
    import hashlib
    hist=[x for x in (history or []) if x in (T,X)]
    if len(hist)>=16:
        prior=hist[-100:]
        t=x=2.0
        for j in range(1,len(prior)):
            if prior[j-1]==prior[-1]:
                if prior[j]==T:t+=1
                else:x+=1
        n=t+x
        if n>=14 and abs(t-x)/n>=.11:
            return _choose(t,x,hist[-1]), 'CHUYỂN TRẠNG THÁI'
        # Short and long class shares can differ. Do not chase a streak blindly.
        a=hist[-24:]
        count=a.count(T)
        if len(a)>=20 and (count>=17 or count<=7):
            return (X if count>=17 else T), 'HIỆU CHỈNH LỆCH CẦU'
    if hist:
        # Alternating hash is only a tie-break, not claimed to forecast dice.
        raw=''.join('T' if x==T else 'X' for x in hist[-32:]).encode()
        b=hashlib.blake2s(raw,digest_size=1).digest()[0]
        return (T if b&1 else X), 'DỮ LIỆU YẾU'
    return T,'KHỞI TẠO'


def select_predict(preds, logs, current_champion=None, history=None):
    """Select a tested expert only with enough prior evidence.

    Champion quality must outperform both chance-level and a trivial
    fixed-side historical baseline by a *margin*, avoiding habitual TÀI picks
    caused by an ensemble of many correlated experts.
    """
    scores={name:_score(list(logs.get(name,()))) for name in preds}
    h=[x for x in (history or []) if x in (T,X)]
    recent=h[-50:]
    # Fixed-side scores are diagnostic benchmark, not a prediction.
    fixed=(max(recent.count(T),recent.count(X))+12)/(len(recent)+24) if len(recent)>=25 else .5
    bar=max(.515,fixed+.018)
    valid=[(v,k) for k,v in scores.items() if v>=bar and len(logs.get(k,()))>=40]
    valid.sort(reverse=True)
    champion=valid[0][1] if valid else None
    if current_champion in preds and current_champion in scores and champion and current_champion!=champion:
        prior=scores[current_champion]
        wins=list(logs.get(current_champion,()))
        if (prior>=bar-.015 and len(wins)>=3 and any(wins[-3:])
                and scores[champion]-prior<.055):
            champion=current_champion
    if champion:
        pick=preds[champion]
        strength=scores[champion]
        n=len(logs.get(champion,()))
        return {'prediction':pick,'champion':champion,'mode':'HỌC CẦU KIỂM CHỨNG',
                'sample_count':n,'historical_score':round(strength,4),
                'baseline_score':round(fixed,4),
                'top':sorted(({'name':k,'score':round(v,4),'n':len(logs.get(k,()))}
                              for k,v in scores.items() if v>=0),
                             key=lambda x:x['score'],reverse=True)[:5]}
    fallback,reason=_fallback_prediction(preds,history)
    return {'prediction':fallback,'champion':None,'mode':reason,
            'sample_count':len(h),'historical_score':.5,
            'baseline_score':round(fixed,4),'top':[]}

def id_contiguous(previous_key, current_key, prev_meta=None, cur_meta=None, board=''):
    """Conservative gap check: do not learn a bridge over missing sessions/shoes."""
    import re
    prev_meta=prev_meta or {};cur_meta=cur_meta or {}
    if board.startswith('baccarat:'):
        if prev_meta.get('shoe')!=cur_meta.get('shoe'):return False
        try:return int(cur_meta['pos'])==int(prev_meta['pos'])+1
        except (KeyError,TypeError,ValueError):return False
    if board.startswith('sunwin:'):
        if not (str(previous_key).isdigit() and str(current_key).isdigit()):return False
        return int(current_key)==int(previous_key)+1
    return False


def trailing_segment(rows,board):
    """rows chronological, tuples (external_key,result,meta)."""
    if not rows:return []
    start=len(rows)-1
    while start>0:
        pre,cur=rows[start-1],rows[start]
        if not id_contiguous(pre[0],cur[0],pre[2],cur[2],board):break
        start-=1
    return rows[start:]


# V6 delegates to a version-tagged expert catalog. Older V5 logs remain
# available for audit but MUST NOT calibrate these changed strategies.
from v6_engine import strategies as strategy_predictions
from v6_engine import select as select_predict
from v6_engine import append_result as record_settled
