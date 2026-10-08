# DEVELOPER THANHTUNG VIP · ONLINE LEARNING ENGINE
# 67 causal binary-sequence strategies consolidated from the V49/V55/V56 engines.
# TÀI/XỈU are internal binary labels; callers may map Banker/Player to them.
import math

MAX_HISTORY = 10000
REFERENCE_PATTERN_COUNTS = {}

def _clamp(v, a, b):
    return max(a, min(b, v))

def _entropy(seq):
    if not seq:
        return 1.0
    p = sum((1 for x in seq if x == 'TÀI')) / len(seq)
    if p <= 0 or p >= 1:
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)

def _opp(side):
    return 'XỈU' if side == 'TÀI' else 'TÀI'

def _run_len(seq):
    if not seq:
        return 0
    n = 1
    for i in range(len(seq) - 2, -1, -1):
        if seq[i] == seq[-1]:
            n += 1
        else:
            break
    return n

def _markov_prediction(seq, order=1):
    if not seq:
        return 'TÀI'
    order = max(1, min(4, int(order)))
    if len(seq) <= order + 2:
        return _opp(seq[-1])
    ctx = tuple(seq[-order:])
    t = x = 1.0
    for i in range(order, len(seq)):
        if tuple(seq[i - order:i]) != ctx:
            continue
        if seq[i] == 'TÀI':
            t += 1
        else:
            x += 1
    return 'TÀI' if t >= x else 'XỈU'

def _suffix_prediction(seq):
    if not seq:
        return 'TÀI'
    for L in (6, 5, 4, 3, 2):
        if len(seq) <= L:
            continue
        motif = tuple(seq[-L:])
        t = x = 0
        for i in range(L, len(seq)):
            if tuple(seq[i - L:i]) != motif:
                continue
            if seq[i] == 'TÀI':
                t += 1
            else:
                x += 1
        if t + x >= 2:
            return 'TÀI' if t >= x else 'XỈU'
    return _markov_prediction(seq, 1)

def _run_hazard_prediction(seq):
    if not seq:
        return 'TÀI'
    side = seq[-1]
    cur = _run_len(seq)
    follow = brk = 1.0
    for i in range(1, len(seq)):
        if seq[i - 1] != side:
            continue
        rl = 1
        j = i - 2
        while j >= 0 and seq[j] == side and (rl < 8):
            rl += 1
            j -= 1
        if abs(rl - cur) > 1:
            continue
        if seq[i] == side:
            follow += 1
        else:
            brk += 1
    return side if follow >= brk else _opp(side)

def _multi_window_prediction(seq):
    if not seq:
        return 'TÀI'
    vote = 0.0
    for w, weight in ((8, 1.0), (16, 1.15), (32, 1.3), (64, 1.1)):
        q = seq[-w:]
        if not q:
            continue
        p = q.count('TÀI') / len(q)
        if p >= 0.68:
            vote -= weight
        elif p >= 0.54:
            vote += weight
        elif p <= 0.32:
            vote += weight
        elif p <= 0.46:
            vote -= weight
    if abs(vote) < 0.1:
        return _markov_prediction(seq, 2)
    return 'TÀI' if vote > 0 else 'XỈU'

def _decayed_transition_prediction(seq, order=2, decay=0.955):
    if not seq:
        return 'TÀI'
    order = max(1, min(4, int(order)))
    if len(seq) <= order + 3:
        return _markov_prediction(seq, order)
    ctx = tuple(seq[-order:])
    t = x = 0.7
    for i in range(order, len(seq)):
        if tuple(seq[i - order:i]) != ctx:
            continue
        age = len(seq) - 1 - i
        w = decay ** age
        if seq[i] == 'TÀI':
            t += w
        else:
            x += w
    return 'TÀI' if t >= x else 'XỈU'

def _motif_weighted_prediction(seq):
    if not seq:
        return 'TÀI'
    vt = vx = 0.0
    for L in (2, 3, 4, 5, 6):
        if len(seq) <= L + 1:
            continue
        motif = tuple(seq[-L:])
        for i in range(L, len(seq)):
            if tuple(seq[i - L:i]) != motif:
                continue
            age = len(seq) - 1 - i
            w = (1.0 + 0.2 * L) * 0.965 ** age
            if seq[i] == 'TÀI':
                vt += w
            else:
                vx += w
    if vt + vx < 1.2:
        return _markov_prediction(seq, 2)
    return 'TÀI' if vt >= vx else 'XỈU'

def _regime_adaptive_prediction(seq):
    if not seq:
        return 'TÀI'
    q = seq[-24:]
    last = q[-1]
    run = _run_len(q)
    flips = sum((1 for i in range(1, len(q)) if q[i] != q[i - 1])) / max(1, len(q) - 1)
    p = q.count('TÀI') / len(q)
    if flips >= 0.7:
        return _opp(last)
    if run >= 3:
        return _run_hazard_prediction(seq)
    if p >= 0.7:
        return 'XỈU'
    if p <= 0.3:
        return 'TÀI'
    if p >= 0.57:
        return 'TÀI'
    if p <= 0.43:
        return 'XỈU'
    return _decayed_transition_prediction(seq, 2)

def _flip_state_markov_prediction(seq):
    if not seq:
        return 'TÀI'
    if len(seq) < 8:
        return _markov_prediction(seq, 1)
    state = 'F' if seq[-1] != seq[-2] else 'R'
    tai = xiu = 1.2
    for i in range(2, len(seq)):
        st = 'F' if seq[i - 1] != seq[i - 2] else 'R'
        if st != state:
            continue
        w = 0.965 ** (len(seq) - 1 - i)
        if seq[i] == 'TÀI':
            tai += w
        else:
            xiu += w
    return 'TÀI' if tai >= xiu else 'XỈU'

def _run_length_markov_prediction(seq):
    if not seq:
        return 'TÀI'
    if len(seq) < 10:
        return _run_hazard_prediction(seq)
    side = seq[-1]
    target = min(_run_len(seq), 6)
    follow = brk = 1.25
    for i in range(2, len(seq)):
        prev = seq[i - 1]
        if prev != side:
            continue
        rl = 1
        j = i - 2
        while j >= 0 and seq[j] == prev and (rl < 6):
            rl += 1
            j -= 1
        if abs(rl - target) > 1:
            continue
        w = 0.97 ** (len(seq) - 1 - i)
        if seq[i] == side:
            follow += w
        else:
            brk += w
    return side if follow >= brk else _opp(side)

def _periodic_match_prediction(seq):
    if not seq:
        return 'TÀI'
    n = len(seq)
    if n < 18:
        return _markov_prediction(seq, 2)
    best_lag = None
    best = -1.0
    q = seq[-min(70, n):]
    for lag in range(2, min(13, len(q) // 3 + 1)):
        hit = tot = 0
        for i in range(lag, len(q)):
            tot += 1
            if q[i] == q[i - lag]:
                hit += 1
        if tot < 10:
            continue
        rate = (hit + 2.5) / (tot + 5)
        score = rate - (0.008 if lag <= 3 else 0)
        if score > best:
            best = score
            best_lag = lag
    return seq[-best_lag] if best_lag else _markov_prediction(seq, 2)

def _dual_horizon_prediction(seq):
    if not seq:
        return 'TÀI'
    q8 = seq[-8:]
    q28 = seq[-28:]
    p8 = q8.count('TÀI') / max(1, len(q8))
    p28 = q28.count('TÀI') / max(1, len(q28))
    short = p8 - 0.5
    long = p28 - 0.5
    if short * long > 0 and abs(short) >= 0.08:
        return 'TÀI' if short > 0 else 'XỈU'
    if abs(short - long) >= 0.28:
        return 'XỈU' if short > 0 else 'TÀI'
    return _decayed_transition_prediction(seq, 2)

def _analog_knn_prediction(seq):
    if not seq:
        return 'TÀI'
    n = len(seq)
    if n < 24:
        return _markov_prediction(seq, 2)
    vt = vx = 0.0
    for L in (4, 5, 6, 7, 8):
        if n <= L + 2:
            continue
        cur = seq[-L:]
        for i in range(L, n - 1):
            past = seq[i - L:i]
            sim = sum((1 for a, b in zip(cur, past) if a == b)) / L
            if sim < 0.75:
                continue
            age = n - 1 - i
            w = sim ** 3 * 0.97 ** age * (1 + 0.06 * L)
            nxt = seq[i]
            if nxt == 'TÀI':
                vt += w
            else:
                vx += w
    if vt + vx < 1.0:
        return _suffix_prediction(seq)
    return 'TÀI' if vt >= vx else 'XỈU'

def _run_survival_prediction(seq):
    if not seq:
        return 'TÀI'
    side = seq[-1]
    cur = min(_run_len(seq), 8)
    runs = []
    rside = seq[0]
    length = 1
    for x in seq[1:]:
        if x == rside:
            length += 1
        else:
            runs.append((rside, length))
            rside = x
            length = 1
    same = [l for sd, l in runs if sd == side and l >= cur]
    if len(same) < 3:
        return _run_length_markov_prediction(seq)
    survive = sum((1 for l in same if l >= cur + 1))
    p = (survive + 2) / (len(same) + 4)
    return side if p >= 0.52 else _opp(side)

def _context_entropy_prediction(seq):
    if not seq:
        return 'TÀI'
    best = None
    for order in (1, 2, 3, 4):
        if len(seq) < order + 12:
            continue
        ctx = tuple(seq[-order:])
        t = x = 1.5
        sample = 0
        for i in range(order, len(seq)):
            if tuple(seq[i - order:i]) != ctx:
                continue
            w = 0.97 ** (len(seq) - 1 - i)
            if seq[i] == 'TÀI':
                t += w
            else:
                x += w
            sample += 1
        if sample < 3:
            continue
        p = t / (t + x)
        ent = 0.0
        for z in (p, 1 - p):
            if z > 0:
                ent -= z * math.log2(z)
        strength = abs(p - 0.5) * (1 - ent * 0.35) * min(1, sample / 10)
        cand = (strength, 'TÀI' if p >= 0.5 else 'XỈU')
        if best is None or cand[0] > best[0]:
            best = cand
    return best[1] if best else _decayed_transition_prediction(seq, 2)

def _bayes_context_prediction(seq):
    if not seq:
        return 'TÀI'
    vt = vx = 0.0
    for order, ow in ((1, 0.7), (2, 1.0), (3, 1.25), (4, 1.45), (5, 1.6)):
        if len(seq) < order + 6:
            continue
        ctx = tuple(seq[-order:])
        t = x = 2.0
        sample = 0
        for i in range(order, len(seq)):
            if tuple(seq[i - order:i]) != ctx:
                continue
            age = len(seq) - 1 - i
            w = 0.972 ** age
            if seq[i] == 'TÀI':
                t += w
            else:
                x += w
            sample += 1
        if sample < 2:
            continue
        p = t / (t + x)
        strength = abs(p - 0.5) * min(1.0, sample / 10) * ow
        if p >= 0.5:
            vt += strength
        else:
            vx += strength
    if vt + vx < 0.04:
        return _decayed_transition_prediction(seq, 2)
    return 'TÀI' if vt >= vx else 'XỈU'

def _horizon_consensus_prediction(seq):
    if not seq:
        return 'TÀI'
    vote = 0.0
    for w, wt in ((6, 1.35), (10, 1.25), (20, 1.1), (40, 0.9), (80, 0.7)):
        q = seq[-w:]
        if len(q) < 4:
            continue
        p = q.count('TÀI') / len(q)
        edge = p - 0.5
        if abs(edge) < 0.04:
            continue
        vote += wt * edge * 2
    if abs(vote) < 0.12:
        return _markov_prediction(seq, 2)
    return 'TÀI' if vote > 0 else 'XỈU'

def _regime_switch_prediction(seq):
    if not seq:
        return 'TÀI'
    q = seq[-32:]
    last = q[-1]
    run = _run_len(q)
    flips = sum((1 for i in range(1, len(q)) if q[i] != q[i - 1])) / max(1, len(q) - 1)
    p = q.count('TÀI') / len(q)
    if flips >= 0.68:
        return _opp(last)
    if flips <= 0.32 and run >= 2:
        return _run_survival_prediction(seq)
    if abs(p - 0.5) >= 0.18:
        return _multi_window_prediction(seq)
    a = _bayes_context_prediction(seq)
    b = _decayed_transition_prediction(seq, 3)
    c = _motif_weighted_prediction(seq)
    return a if a == b or a == c else b if b == c else _markov_prediction(seq, 2)

def _lag_ensemble_prediction(seq):
    if not seq:
        return 'TÀI'
    n = len(seq)
    if n < 24:
        return _periodic_match_prediction(seq)
    vt = vx = 0.0
    for lag in range(2, min(16, n // 3 + 1)):
        hit = tot = 0
        start = max(lag, n - 90)
        for i in range(start, n):
            tot += 1
            hit += 1 if seq[i] == seq[i - lag] else 0
        if tot < 10:
            continue
        rate = (hit + 3) / (tot + 6)
        edge = rate - 0.5
        if abs(edge) < 0.035:
            continue
        pred = seq[-lag] if edge > 0 else _opp(seq[-lag])
        w = abs(edge) * (1.0 / (1 + 0.035 * lag))
        if pred == 'TÀI':
            vt += w
        else:
            vx += w
    if vt + vx < 0.035:
        return _periodic_match_prediction(seq)
    return 'TÀI' if vt >= vx else 'XỈU'

def _vom_context6_prediction(seq):
    if not seq:
        return 'TÀI'
    vt = vx = 0.0
    n = len(seq)
    for order, ow in ((2, 0.8), (3, 1.0), (4, 1.18), (5, 1.35), (6, 1.5), (7, 1.6), (8, 1.68)):
        if n < order + 12:
            continue
        ctx = tuple(seq[-order:])
        t = x = 1.8
        support = 0.0
        for i in range(order, n):
            if tuple(seq[i - order:i]) != ctx:
                continue
            age = n - 1 - i
            w = 0.5 ** (age / 260.0)
            support += w
            if seq[i] == 'TÀI':
                t += w
            else:
                x += w
        if support < 2.0:
            continue
        p = t / (t + x)
        edge = (p - 0.5) * 2.0
        weight = ow * min(1.0, support / 18.0) * min(1.0, abs(edge) * 3.0 + 0.15)
        if p >= 0.5:
            vt += weight * max(0.05, abs(edge))
        else:
            vx += weight * max(0.05, abs(edge))
    if vt + vx < 0.05:
        return _bayes_context_prediction(seq)
    return 'TÀI' if vt >= vx else 'XỈU'

def _long_memory_bayes_prediction(seq):
    if not seq:
        return 'TÀI'
    q = seq[-min(len(seq), MAX_HISTORY):]
    n = len(q)
    vt = vx = 0.0
    for order, ow in ((1, 0.55), (2, 0.75), (3, 1.0), (4, 1.2), (5, 1.35), (6, 1.48)):
        if n < order + 20:
            continue
        ctx = tuple(q[-order:])
        t = x = 3.0
        support = 0.0
        for i in range(order, n):
            if tuple(q[i - order:i]) != ctx:
                continue
            age = n - 1 - i
            w = 0.5 ** (age / 520.0)
            support += w
            if q[i] == 'TÀI':
                t += w
            else:
                x += w
        if support < 3:
            continue
        p = t / (t + x)
        edge = (p - 0.5) * 2
        rel = (1 - math.exp(-support / 25.0)) * ow
        if p >= 0.5:
            vt += rel * abs(edge)
        else:
            vx += rel * abs(edge)
    if vt + vx < 0.035:
        return _decayed_transition_prediction(seq, 3)
    return 'TÀI' if vt >= vx else 'XỈU'

def _run_profile_long_prediction(seq):
    if not seq:
        return 'TÀI'
    q = seq[-min(len(seq), MAX_HISTORY):]
    side = q[-1]
    cur = min(_run_len(q), 12)
    same = brk = 1.5
    support = 0
    for i in range(2, len(q)):
        prev = q[i - 1]
        rl = 1
        j = i - 2
        while j >= 0 and q[j] == prev and (rl < 12):
            rl += 1
            j -= 1
        if prev != side or abs(rl - cur) > 1:
            continue
        age = len(q) - 1 - i
        w = 0.5 ** (age / 650.0)
        support += 1
        if q[i] == prev:
            same += w
        else:
            brk += w
    if support < 6:
        return _run_survival_prediction(seq)
    return side if same >= brk else _opp(side)

def _multiscale_transition_prediction(seq):
    if not seq:
        return 'TÀI'
    votes = []
    for w, wt in ((32, 1.4), (64, 1.3), (128, 1.18), (256, 1.04), (512, 0.9), (1000, 0.78), (2000, 0.66), (5000, 0.52), (10000, 0.4)):
        q = seq[-w:]
        if len(q) < min(24, w):
            continue
        a = _decayed_transition_prediction(q, 2, 0.972 if w <= 128 else 0.988)
        b = _markov_prediction(q, 3)
        pred = a if a == b else _bayes_context_prediction(q)
        votes.append((pred, wt))
    if not votes:
        return _markov_prediction(seq, 2)
    vt = sum((w for p, w in votes if p == 'TÀI'))
    vx = sum((w for p, w in votes if p == 'XỈU'))
    return 'TÀI' if vt >= vx else 'XỈU'

def _majority3(a, b, c):
    if a == b or a == c:
        return a
    if b == c:
        return b
    return b

def _changepoint_adaptive_prediction(seq):
    if not seq:
        return 'TÀI'
    if len(seq) < 36:
        return _regime_switch_prediction(seq)
    r = seq[-16:]
    old = seq[-48:-16] if len(seq) >= 48 else seq[:-16]
    pr = r.count('TÀI') / len(r)
    po = old.count('TÀI') / max(1, len(old))
    fr = sum((1 for i in range(1, len(r)) if r[i] != r[i - 1])) / max(1, len(r) - 1)
    fo = sum((1 for i in range(1, len(old)) if old[i] != old[i - 1])) / max(1, len(old) - 1)
    shift = abs(pr - po) + 0.65 * abs(fr - fo)
    if shift >= 0.28:
        q = seq[-48:]
        return _majority3(_decayed_transition_prediction(q, 2, 0.94), _bayes_context_prediction(q), _regime_switch_prediction(q))
    return _majority3(_long_memory_bayes_prediction(seq), _multiscale_transition_prediction(seq), _bayes_context_prediction(seq))

def _wilson_lower(wins, total, z=1.2816):
    if total <= 0:
        return 0.0
    p = wins / total
    z2 = z * z
    den = 1 + z2 / total
    centre = p + z2 / (2 * total)
    spread = z * math.sqrt(max(0.0, p * (1 - p) / total + z2 / (4 * total * total)))
    return (centre - spread) / den

def _wilson_context_prediction(seq):
    if not seq:
        return 'TÀI'
    n = len(seq)
    best = None
    for order in range(2, 10):
        if n < order + 12:
            continue
        ctx = tuple(seq[-order:])
        t = x = 0
        for i in range(order, n):
            if tuple(seq[i - order:i]) != ctx:
                continue
            if seq[i] == 'TÀI':
                t += 1
            else:
                x += 1
        total = t + x
        if total < 4:
            continue
        maj = max(t, x)
        side = 'TÀI' if t >= x else 'XỈU'
        lower = _wilson_lower(maj, total)
        edge = maj / total - 0.5
        score = (lower - 0.5) * min(1.0, total / 28.0) * (1 + 0.06 * order) + edge * 0.12
        cand = (score, total, order, side)
        if best is None or cand[:3] > best[:3]:
            best = cand
    if not best or best[0] <= 0.002:
        return _bayes_context_prediction(seq)
    return best[3]

def _knn_recency_prediction(seq):
    if not seq:
        return 'TÀI'
    n = len(seq)
    if n < 32:
        return _analog_knn_prediction(seq)
    candidates = []
    for L in (5, 6, 8, 10, 12):
        if n <= L + 3:
            continue
        cur = seq[-L:]
        for i in range(L, n - 1):
            past = seq[i - L:i]
            sim = sum((1 for a, b in zip(cur, past) if a == b)) / L
            if sim < 0.7:
                continue
            age = n - 1 - i
            w = sim ** 4 * 0.5 ** (age / 360.0) * (1 + 0.035 * L)
            candidates.append((w, seq[i]))
    if not candidates:
        return _analog_knn_prediction(seq)
    candidates.sort(reverse=True, key=lambda z: z[0])
    candidates = candidates[:48]
    vt = sum((w for w, p in candidates if p == 'TÀI'))
    vx = sum((w for w, p in candidates if p == 'XỈU'))
    if vt + vx < 0.9:
        return _analog_knn_prediction(seq)
    return 'TÀI' if vt >= vx else 'XỈU'

def _run_matrix_prediction(seq):
    if not seq:
        return 'TÀI'
    side = seq[-1]
    cur = min(_run_len(seq), 6)
    same = brk = 2.0
    support = 0.0
    n = len(seq)
    for i in range(2, n):
        prev = seq[i - 1]
        rl = 1
        j = i - 2
        while j >= 0 and seq[j] == prev and (rl < 6):
            rl += 1
            j -= 1
        if prev != side or min(rl, 6) != cur:
            continue
        age = n - 1 - i
        w = 0.5 ** (age / 420.0)
        support += w
        if seq[i] == prev:
            same += w
        else:
            brk += w
    if support < 3.0:
        return _run_profile_long_prediction(seq)
    return side if same >= brk else _opp(side)

def _entropy_gate_prediction(seq):
    if not seq:
        return 'TÀI'
    q32 = seq[-32:]
    q128 = seq[-128:]
    h32 = _entropy(q32)
    h128 = _entropy(q128)
    flips = sum((1 for i in range(1, len(q32)) if q32[i] != q32[i - 1])) / max(1, len(q32) - 1)
    p32 = q32.count('TÀI') / max(1, len(q32))
    p128 = q128.count('TÀI') / max(1, len(q128))
    if h32 < 0.78 and _run_len(q32) >= 3:
        return _run_matrix_prediction(seq)
    if flips >= 0.7:
        return _opp(q32[-1])
    if abs(p32 - 0.5) >= 0.16 and abs(p128 - 0.5) >= 0.08 and ((p32 - 0.5) * (p128 - 0.5) > 0):
        return 'TÀI' if p32 > 0.5 else 'XỈU'
    if h32 - h128 >= 0.1:
        return _changepoint_adaptive_prediction(seq)
    return _wilson_context_prediction(seq)

def _cross_horizon_bayes_prediction(seq):
    if not seq:
        return 'TÀI'
    vt = vx = 0.0
    for w, wt in ((24, 1.35), (48, 1.22), (96, 1.08), (192, 0.92), (384, 0.78), (768, 0.64), (1500, 0.5), (3000, 0.38)):
        q = seq[-w:]
        if len(q) < min(20, w):
            continue
        a = _bayes_context_prediction(q)
        b = _decayed_transition_prediction(q, 3, 0.965 if w <= 96 else 0.986)
        pred = a if a == b else _wilson_context_prediction(q)
        p = q.count('TÀI') / len(q)
        stability = 1 - min(0.35, abs(p - 0.5) * 0.7)
        ww = wt * stability
        if pred == 'TÀI':
            vt += ww
        else:
            vx += ww
    if vt + vx < 0.5:
        return _bayes_context_prediction(seq)
    return 'TÀI' if vt >= vx else 'XỈU'

def _reference_allowed(board):
    return bool(board) and (not str(board).startswith('baccarat:')) and (str(board) != 'lc79:xocdia')

def _reference_pattern_signal(seq):
    if not seq:
        return {'ready': False, 'prediction': 'TÀI', 'score': 0.0, 'support': 0, 'length': 0, 'p_tai': 0.5}
    tx = ''.join(('T' if x == 'TÀI' else 'X' for x in seq[-8:]))
    num = den = 0.0
    best_support = 0
    best_len = 0
    best_p = 0.5
    used = []
    for L in range(min(8, len(tx)), 1, -1):
        key = tx[-L:]
        pair = REFERENCE_PATTERN_COUNTS.get(key)
        if not pair:
            continue
        t, x = pair
        support = t + x
        min_support = 4 if L >= 7 else 5 if L >= 5 else 7
        if support < min_support:
            continue
        p = (t + 3.0) / (support + 6.0)
        edge = (p - 0.5) * 2.0
        reliability = (1 - math.exp(-support / 14.0)) * (L / 8.0) ** 1.35
        w = reliability * (0.38 + 0.62 * min(1.0, abs(edge) * 2.4))
        num += edge * w
        den += w
        used.append((L, key, support, p, edge, w))
        if L > best_len or (L == best_len and support > best_support):
            best_len = L
            best_support = support
            best_p = p
    if den <= 0:
        pred = _markov_prediction(seq, 2)
        return {'ready': False, 'prediction': pred, 'score': 0.0, 'support': 0, 'length': 0, 'p_tai': 0.5}
    score = _clamp(num / den, -0.72, 0.72)
    pred = 'TÀI' if score >= 0 else 'XỈU'
    return {'ready': True, 'prediction': pred, 'score': round(score, 4), 'support': best_support, 'length': best_len, 'p_tai': round((score + 1) / 2, 4), 'best_p_tai': round(best_p, 4), 'contexts': len(used)}

def _reference_pattern_prediction(seq):
    return _reference_pattern_signal(seq).get('prediction') or _markov_prediction(seq, 2)

def _js_randomness_score(seq):
    q = list(seq[-15:])
    if len(q) < 10:
        return 0.5
    changes = sum((1 for i in range(1, len(q)) if q[i] != q[i - 1]))
    change_ratio = changes / max(1, len(q) - 1)
    t = q.count('TÀI')
    x = len(q) - t
    distribution = abs(t - x) / len(q)
    p = t / len(q)
    ent = 0.0
    for z in (p, 1 - p):
        if z > 0:
            ent -= z * math.log2(z)
    return _clamp(change_ratio * 0.4 + (1 - distribution) * 0.3 + ent * 0.3, 0, 1)

def _js_break_signal(seq):
    if not seq:
        return {'prediction': 'TÀI', 'p_break': 0.5, 'support': 0, 'run': 0}
    side = seq[-1]
    cur = max(1, min(_run_len(seq), 8))
    opportunities = breaks = 0
    for i in range(4, len(seq)):
        prev = seq[i - 1]
        rl = 1
        j = i - 2
        while j >= 0 and seq[j] == prev and (rl < 8):
            rl += 1
            j -= 1
        if rl < 3 or abs(rl - cur) > 1:
            continue
        opportunities += 1
        if seq[i] != prev:
            breaks += 1
    ro = rb = 0
    for i in range(max(4, len(seq) - 18), len(seq)):
        prev = seq[i - 1]
        rl = 1
        j = i - 2
        while j >= 0 and seq[j] == prev and (rl < 8):
            rl += 1
            j -= 1
        if rl < 3:
            continue
        ro += 1
        rb += 1 if seq[i] != prev else 0
    p_global = (breaks + 3) / (opportunities + 6)
    p_recent = (rb + 2) / (ro + 4) if ro else 0.5
    length_prior = _clamp(0.42 + 0.035 * max(0, cur - 2), 0.42, 0.68)
    p = _clamp(0.55 * p_global + 0.25 * p_recent + 0.2 * length_prior, 0.18, 0.82)
    pred = _opp(side) if p >= 0.54 else side
    return {'prediction': pred, 'p_break': round(p, 4), 'support': opportunities, 'run': cur}

def _js_break_calibrator_prediction(seq):
    return _js_break_signal(seq)['prediction']

def _js_trend_blend_prediction(seq):
    if not seq:
        return 'TÀI'
    short = seq[-5:]
    long = seq[-20:]
    q12 = seq[-12:]

    def edge(q):
        return (q.count('TÀI') - q.count('XỈU')) / max(1, len(q))
    es = edge(short)
    el = edge(long)
    e12 = edge(q12)
    trend = 'TÀI' if es + el >= 0 else 'XỈU'
    trend_strength = 0.62 * abs(es) + 0.38 * abs(el)
    meanrev = _opp('TÀI' if e12 > 0 else 'XỈU') if abs(e12) >= 0.34 else None
    br = _js_break_signal(seq)
    vt = vx = 0.0

    def add(pred, w):
        nonlocal vt, vx
        if pred == 'TÀI':
            vt += w
        elif pred == 'XỈU':
            vx += w
    add(trend, 0.85 + trend_strength)
    if meanrev:
        add(meanrev, 0.55 + abs(e12) * 0.55)
    add(br['prediction'], 0.62 + abs(br['p_break'] - 0.5) * 1.1)
    s3 = seq[-3:]
    add('TÀI' if s3.count('TÀI') >= 2 else 'XỈU', 0.62)
    return 'TÀI' if vt >= vx else 'XỈU'

def _js_ultra_stack_prediction(seq, use_reference=True):
    if not seq:
        return 'TÀI'
    rnd = _js_randomness_score(seq)
    signals = [(_js_trend_blend_prediction(seq), 1.0), (_js_break_calibrator_prediction(seq), 0.95), (_bayes_context_prediction(seq), 1.1), (_context_entropy_prediction(seq), 0.92), (_regime_switch_prediction(seq), 1.0)]
    if use_reference:
        rs = _reference_pattern_signal(seq)
        if rs.get('ready'):
            rw = (0.55 + min(0.55, abs(float(rs.get('score', 0))) * 0.9)) * (0.65 if rnd > 0.72 else 1.0)
            signals.append((rs['prediction'], rw))
    if rnd > 0.72:
        signals += [(_multi_window_prediction(seq), 0.72), (_markov_prediction(seq, 2), 0.78)]
    vt = vx = 0.0
    for pred, w in signals:
        if pred == 'TÀI':
            vt += w
        else:
            vx += w
    return 'TÀI' if vt >= vx else 'XỈU'

def _dirichlet_vom_prediction(seq):
    """Variable-order Markov 1..10 with Dirichlet smoothing + recency evidence."""
    if not seq:
        return 'TÀI'
    n = len(seq)
    vt = vx = 0.0
    max_order = min(10, max(1, n // 5))
    for order in range(1, max_order + 1):
        if n <= order + 3:
            continue
        ctx = tuple(seq[-order:])
        t = x = 1.8
        ev = 0.0
        half = max(28.0, 72.0 - order * 3.0)
        for i in range(order, n):
            if tuple(seq[i - order:i]) != ctx:
                continue
            age = n - 1 - i
            w = 0.5 ** (age / half)
            if seq[i] == 'TÀI':
                t += w
            else:
                x += w
            ev += w
        if ev < 1.1:
            continue
        edge = (t - x) / (t + x)
        evidence = (1 - math.exp(-ev / 4.0)) * min(1.35, 0.72 + 0.075 * order)
        if edge >= 0:
            vt += abs(edge) * evidence
        else:
            vx += abs(edge) * evidence
    if vt + vx < 0.025:
        return _markov_prediction(seq, 2)
    return 'TÀI' if vt >= vx else 'XỈU'

def _sequential_change_prediction(seq):
    """Detect distribution/transition drift and shorten memory after a change."""
    if not seq:
        return 'TÀI'
    n = len(seq)
    if n < 36:
        return _decayed_transition_prediction(seq, 2)

    def feats(q):
        if len(q) < 3:
            return (0.5, 0.5, 0.5)
        pt = q.count('TÀI') / len(q)
        same = sum((1 for i in range(1, len(q)) if q[i] == q[i - 1])) / max(1, len(q) - 1)
        return (pt, same, 1 - same)
    recent = seq[-24:]
    older = seq[-104:-24] if n >= 104 else seq[:-24]
    fr = feats(recent)
    fo = feats(older)
    drift = sum((abs(a - b) for a, b in zip(fr, fo))) / 3.0
    if drift >= 0.17:
        return _regime_switch_prediction(seq[-80:])
    if drift >= 0.1:
        a = _changepoint_adaptive_prediction(seq)
        b = _dirichlet_vom_prediction(seq[-220:])
        return a if a == b else _decayed_transition_prediction(seq, 2)
    return _dirichlet_vom_prediction(seq)

def _motif_survival_prediction(seq):
    """Suffix matching 3..12 with Beta smoothing, age decay and support weighting."""
    if not seq:
        return 'TÀI'
    n = len(seq)
    vt = vx = 0.0
    for L in range(3, min(12, n - 4) + 1):
        motif = tuple(seq[-L:])
        t = x = 1.4
        ev = 0.0
        for i in range(L, n):
            if tuple(seq[i - L:i]) != motif:
                continue
            age = n - 1 - i
            w = 0.5 ** (age / max(36.0, 92.0 - L * 3.0))
            if seq[i] == 'TÀI':
                t += w
            else:
                x += w
            ev += w
        if ev < 1.0:
            continue
        edge = (t - x) / (t + x)
        strength = (1 - math.exp(-ev / 3.6)) * (0.66 + 0.055 * L)
        if edge >= 0:
            vt += abs(edge) * strength
        else:
            vx += abs(edge) * strength
    if vt + vx < 0.02:
        return _suffix_prediction(seq)
    return 'TÀI' if vt >= vx else 'XỈU'

def _regime_posterior_prediction(seq):
    """Soft mixture over run / alternating / biased / mixed regimes."""
    if not seq:
        return 'TÀI'
    q = seq[-64:]
    run = _run_len(q)
    flips = sum((1 for i in range(1, len(q)) if q[i] != q[i - 1])) / max(1, len(q) - 1)
    bias = abs(q.count('TÀI') - q.count('XỈU')) / max(1, len(q))
    h = _entropy(q)
    prun = math.exp(2.0 * min(1, run / 5) + 1.4 * max(0, 0.48 - flips))
    palt = math.exp(3.0 * max(0, flips - 0.52))
    pbias = math.exp(4.0 * max(0, bias - 0.12))
    pmix = math.exp(1.8 * max(0, h - 0.84))
    z = prun + palt + pbias + pmix
    votes = [(_run_hazard_prediction(seq), prun / z), (_opp(seq[-1]), palt / z), (_multi_window_prediction(seq), pbias / z), (_bayes_context_prediction(seq), pmix / z)]
    vt = sum((w for p, w in votes if p == 'TÀI'))
    vx = sum((w for p, w in votes if p == 'XỈU'))
    return 'TÀI' if vt >= vx else 'XỈU'

def _multiresolution_edge_prediction(seq):
    """Shrinked edge over 8..1024 horizons."""
    if not seq:
        return 'TÀI'
    n = len(seq)
    vt = vx = 0.0
    for k, wsize in enumerate((8, 16, 32, 64, 128, 256, 512, 1024)):
        if n < min(8, wsize):
            continue
        q = seq[-min(n, wsize):]
        m = len(q)
        raw = (q.count('TÀI') - q.count('XỈU')) / m
        shr = raw * (m / (m + 18.0))
        wt = 1.18 / (1 + 0.18 * k) * (0.72 + 0.28 * min(1, m / 128))
        if shr >= 0:
            vt += abs(shr) * wt
        else:
            vx += abs(shr) * wt
    if vt + vx < 0.02:
        return _multi_window_prediction(seq)
    return 'TÀI' if vt >= vx else 'XỈU'

def _bayes_run_mixture_prediction(seq):
    """Hierarchical continuation/break model by side and run length, blended with context."""
    if not seq:
        return 'TÀI'
    side = seq[-1]
    cur = min(_run_len(seq), 12)
    cont = brk = 2.0
    for i in range(1, len(seq)):
        prev = seq[i - 1]
        rl = 1
        j = i - 2
        while j >= 0 and seq[j] == prev and (rl < 12):
            rl += 1
            j -= 1
        if prev != side:
            continue
        d = abs(rl - cur)
        if d > 2:
            continue
        w = (1.0, 0.62, 0.34)[d]
        age = len(seq) - 1 - i
        w *= 0.5 ** (age / 180.0)
        if seq[i] == side:
            cont += w
        else:
            brk += w
    pcont = cont / (cont + brk)
    run_pred = side if pcont >= 0.5 else _opp(side)
    ctx = _dirichlet_vom_prediction(seq)
    if abs(pcont - 0.5) >= 0.12:
        return run_pred
    return run_pred if run_pred == ctx else _regime_posterior_prediction(seq)

def _ctx_prob_weighted(seq, order, max_scan=6000):
    """Recency-weighted Beta-smoothed P(TÀI | context)."""
    n = len(seq)
    if n <= order:
        return (0.5, 0.0)
    ctx = tuple(seq[-order:])
    t = x = 0.0
    support = 0.0
    start = max(order, n - max_scan)
    tau = max(120.0, min(1800.0, max_scan / 2.2))
    for i in range(start, n):
        if tuple(seq[i - order:i]) != ctx:
            continue
        age = n - i
        w = math.exp(-age / tau)
        support += w
        if seq[i] == 'TÀI':
            t += w
        else:
            x += w
    p = (t + 2.0) / (t + x + 4.0)
    return (p, support)

def _ctw_approx_prediction(seq):
    if len(seq) < 8:
        return _markov_prediction(seq, 1)
    logit = 0.0
    den = 0.0
    for k in range(1, min(12, len(seq) - 1) + 1):
        p, sup = _ctx_prob_weighted(seq, k)
        if sup < 0.8:
            continue
        strength = abs(p - 0.5) * 2
        w = (1.0 + k * 0.16) * (sup / (sup + 5.0)) * (0.25 + 0.75 * strength)
        logit += (p - 0.5) * w
        den += w
    if den <= 0:
        return _bayes_context_prediction(seq)
    return 'TÀI' if logit >= 0 else 'XỈU'

def _hierarchical_bayes_prediction(seq):
    if len(seq) < 10:
        return _markov_prediction(seq, 1)
    base = (seq[-512:].count('TÀI') + 6) / (len(seq[-512:]) + 12)
    p = base
    for k in range(1, min(10, len(seq) - 1) + 1):
        pk, sup = _ctx_prob_weighted(seq, k, 5000)
        shrink = sup / (sup + 7.0 + 1.8 * k)
        p = (1 - shrink) * p + shrink * pk
    return 'TÀI' if p >= 0.5 else 'XỈU'

def _transition_drift_prediction(seq):
    if len(seq) < 12:
        return _markov_prediction(seq, 1)
    last = seq[-1]

    def p_for(window):
        q = seq[-window:]
        a = b = 0.0
        for i in range(1, len(q)):
            if q[i - 1] != last:
                continue
            w = 0.55 + 0.45 * (i / max(1, len(q) - 1))
            if q[i] == 'TÀI':
                a += w
            else:
                b += w
        return ((a + 2) / (a + b + 4), a + b)
    vals = []
    for w in (24, 64, 160, 512, 1600):
        if len(seq) >= min(12, w // 2):
            vals.append(p_for(w))
    if not vals:
        return _markov_prediction(seq, 1)
    longp = vals[-1][0]
    score = 0.0
    den = 0.0
    for idx, (p, sup) in enumerate(vals):
        rec = (len(vals) - idx) / len(vals)
        drift = abs(p - longp)
        wt = sup / (sup + 8) * (1.15 if idx == 0 and drift > 0.12 else 1.0) * (0.75 + 0.5 * rec)
        score += (p - 0.5) * wt
        den += wt
    return 'TÀI' if score >= 0 else 'XỈU'

def _run_context_joint_prediction(seq):
    if len(seq) < 12:
        return _run_hazard_prediction(seq)
    last = seq[-1]
    run = min(_run_len(seq), 8)
    t = x = 0.0
    n = len(seq)
    for i in range(4, n):
        r = 1
        j = i - 2
        while j >= 0 and seq[j] == seq[i - 1] and (r < 8):
            r += 1
            j -= 1
        if seq[i - 1] != last or min(r, 8) != run:
            continue
        curflip = seq[-1] != seq[-2]
        histflip = seq[i - 1] != seq[i - 2]
        if curflip != histflip:
            continue
        w = math.exp(-(n - i) / 900.0)
        if seq[i] == 'TÀI':
            t += w
        else:
            x += w
    if t + x < 2.0:
        return _bayes_run_mixture_prediction(seq)
    p = (t + 2) / (t + x + 4)
    return 'TÀI' if p >= 0.5 else 'XỈU'

def _spectral_lag_prediction(seq):
    q = seq[-768:]
    if len(q) < 24:
        return _periodic_match_prediction(seq)
    vt = vx = 0.0
    for lag in range(2, min(40, len(q) // 3) + 1):
        matches = sum((1 for i in range(lag, len(q)) if q[i] == q[i - lag]))
        total = len(q) - lag
        if total < 18:
            continue
        rate = (matches + 4 * 0.5) / (total + 4)
        edge = abs(rate - 0.5)
        if edge < 0.025:
            continue
        pred = q[-lag] if rate >= 0.5 else _opp(q[-lag])
        wt = edge * math.sqrt(total) / (1 + 0.035 * lag)
        if pred == 'TÀI':
            vt += wt
        else:
            vx += wt
    if vt + vx <= 0:
        return _lag_ensemble_prediction(seq)
    return 'TÀI' if vt >= vx else 'XỈU'

def _robust_stack_prediction(seq):
    experts = [_ctw_approx_prediction(seq), _hierarchical_bayes_prediction(seq), _transition_drift_prediction(seq), _run_context_joint_prediction(seq), _spectral_lag_prediction(seq), _dirichlet_vom_prediction(seq), _cross_horizon_bayes_prediction(seq), _regime_posterior_prediction(seq), _entropy_gate_prediction(seq), _bayes_run_mixture_prediction(seq)]
    t = experts.count('TÀI')
    x = len(experts) - t
    if t == x:
        return _ctw_approx_prediction(seq)
    return 'TÀI' if t > x else 'XỈU'

def _pure_strategy_predictions(seq, board=None):
    """Causal predictors dùng riêng để walk-forward, không đọc future/DB feedback."""
    if not seq:
        return {}
    last = seq[-1]
    run = _run_len(seq)
    q6 = seq[-6:]
    flips = sum((1 for i in range(1, len(q6)) if q6[i] != q6[i - 1]))
    alt = flips / max(1, len(q6) - 1)
    p20 = seq[-20:].count('TÀI') / max(1, len(seq[-20:]))
    p12 = seq[-12:].count('TÀI') / max(1, len(seq[-12:]))
    return {'FOLLOW_LAST': last, 'REVERSE_LAST': _opp(last), 'ALTERNATING_PATTERN': _opp(last) if alt >= 0.6 else _markov_prediction(seq, 1), 'RUN_BREAK': _opp(last) if run >= 3 else _markov_prediction(seq, 1), 'RUN_FOLLOW': last if 2 <= run <= 3 else _opp(last) if run >= 5 else _markov_prediction(seq, 1), 'BIAS_MEAN_REVERSION': 'XỈU' if p20 >= 0.6 else 'TÀI' if p20 <= 0.4 else _opp(last), 'BIAS_MOMENTUM': 'TÀI' if p12 >= 0.58 else 'XỈU' if p12 <= 0.42 else last, 'MARKOV_TRANSITION': _markov_prediction(seq, 1), 'HIGH_ORDER_MARKOV': _markov_prediction(seq, 3), 'MARKOV_ORDER2': _markov_prediction(seq, 2), 'RUN_HAZARD': _run_hazard_prediction(seq), 'MULTI_WINDOW': _multi_window_prediction(seq), 'DECAYED_TRANSITION': _decayed_transition_prediction(seq, 2), 'REGIME_ADAPTIVE': _regime_adaptive_prediction(seq), 'MOTIF_WEIGHTED': _motif_weighted_prediction(seq), 'FLIP_STATE_MARKOV': _flip_state_markov_prediction(seq), 'RUN_LENGTH_MARKOV': _run_length_markov_prediction(seq), 'PERIODIC_MATCH': _periodic_match_prediction(seq), 'DUAL_HORIZON': _dual_horizon_prediction(seq), 'ANALOG_KNN': _analog_knn_prediction(seq), 'RUN_SURVIVAL': _run_survival_prediction(seq), 'CONTEXT_ENTROPY': _context_entropy_prediction(seq), 'BAYES_CONTEXT': _bayes_context_prediction(seq), 'HORIZON_CONSENSUS': _horizon_consensus_prediction(seq), 'REGIME_SWITCH': _regime_switch_prediction(seq), 'LAG_ENSEMBLE': _lag_ensemble_prediction(seq), 'REFERENCE_PATTERN_PRIOR': _reference_pattern_prediction(seq) if _reference_allowed(board) else _bayes_context_prediction(seq), 'JS_TREND_BLEND': _js_trend_blend_prediction(seq), 'JS_BREAK_CALIBRATOR': _js_break_calibrator_prediction(seq), 'JS_ULTRA_STACK': _js_ultra_stack_prediction(seq, _reference_allowed(board)), 'VOM_CONTEXT_6': _vom_context6_prediction(seq), 'LONG_MEMORY_BAYES': _long_memory_bayes_prediction(seq), 'RUN_PROFILE_LONG': _run_profile_long_prediction(seq), 'MULTISCALE_TRANSITION': _multiscale_transition_prediction(seq), 'CHANGEPOINT_ADAPTIVE': _changepoint_adaptive_prediction(seq), 'WILSON_CONTEXT': _wilson_context_prediction(seq), 'KNN_RECENCY': _knn_recency_prediction(seq), 'RUN_MATRIX': _run_matrix_prediction(seq), 'ENTROPY_GATE': _entropy_gate_prediction(seq), 'CROSS_HORIZON_BAYES': _cross_horizon_bayes_prediction(seq), 'DIRICHLET_VOM': _dirichlet_vom_prediction(seq), 'SEQUENTIAL_CHANGE': _sequential_change_prediction(seq), 'MOTIF_SURVIVAL': _motif_survival_prediction(seq), 'REGIME_POSTERIOR': _regime_posterior_prediction(seq), 'MULTIRESOLUTION_EDGE': _multiresolution_edge_prediction(seq), 'BAYES_RUN_MIXTURE': _bayes_run_mixture_prediction(seq), 'CTW_APPROX': _ctw_approx_prediction(seq), 'HIERARCHICAL_BAYES': _hierarchical_bayes_prediction(seq), 'TRANSITION_DRIFT': _transition_drift_prediction(seq), 'RUN_CONTEXT_JOINT': _run_context_joint_prediction(seq), 'SPECTRAL_LAG': _spectral_lag_prediction(seq), 'ROBUST_STACK': _robust_stack_prediction(seq), 'SUFFIX_CONTEXT': _suffix_prediction(seq)}

# The old reference-pattern table came from a different historical source.
# For online learning we deliberately disable that static prior and replace it
# with the live pattern-memory layer in web_admin_bot.py.
def _reference_allowed(board):
    return False

def _reference_pattern_signal(seq):
    return {'ready':False,'prediction':_markov_prediction(seq,2) if seq else 'TÀI',
            'score':0.0,'support':0,'length':0,'p_tai':0.5}

def _reference_pattern_prediction(seq):
    return _markov_prediction(seq,2) if seq else 'TÀI'

_v49_pure_strategy_predictions = _pure_strategy_predictions

def _majority(vals, fallback='TÀI'):
    vals=[v for v in vals if v in ('TÀI','XỈU')]
    if not vals:
        return fallback
    t=vals.count('TÀI'); x=len(vals)-t
    if t==x:
        return fallback
    return 'TÀI' if t>x else 'XỈU'

def _v55_ewma_markov(seq):
    return _majority([
        _decayed_transition_prediction(seq,1),
        _decayed_transition_prediction(seq,2),
        _markov_prediction(seq,2),
        _markov_prediction(seq,3),
    ], _markov_prediction(seq,1))

def _v55_local_global_bayes(seq):
    return _majority([
        _bayes_context_prediction(seq),
        _long_memory_bayes_prediction(seq),
        _cross_horizon_bayes_prediction(seq),
        _hierarchical_bayes_prediction(seq),
    ], _bayes_context_prediction(seq))

def _v55_motif_knn(seq):
    return _majority([
        _motif_weighted_prediction(seq),
        _motif_survival_prediction(seq),
        _knn_recency_prediction(seq),
        _suffix_prediction(seq),
    ], _motif_weighted_prediction(seq))

def _v55_run_regime(seq):
    return _majority([
        _run_hazard_prediction(seq),
        _run_length_markov_prediction(seq),
        _run_survival_prediction(seq),
        _regime_posterior_prediction(seq),
        _run_context_joint_prediction(seq),
    ], _run_hazard_prediction(seq))

def _v55_drift_consensus(seq):
    return _majority([
        _changepoint_adaptive_prediction(seq),
        _sequential_change_prediction(seq),
        _transition_drift_prediction(seq),
        _multiresolution_edge_prediction(seq),
    ], _sequential_change_prediction(seq))

def _v55_calibrated_stack(seq):
    return _majority([
        _robust_stack_prediction(seq),
        _ctw_approx_prediction(seq),
        _hierarchical_bayes_prediction(seq),
        _entropy_gate_prediction(seq),
        _horizon_consensus_prediction(seq),
    ], _robust_stack_prediction(seq))

def _v56_context_drift(seq):
    fb=_decayed_transition_prediction(seq,1)
    return _majority([
        _decayed_transition_prediction(seq,2),
        _transition_drift_prediction(seq),
        _ctw_approx_prediction(seq),
        _hierarchical_bayes_prediction(seq)
    ],fb)

def _v56_motif_lag(seq):
    fb=_motif_weighted_prediction(seq)
    return _majority([
        _motif_weighted_prediction(seq),
        _motif_survival_prediction(seq),
        _lag_ensemble_prediction(seq),
        _spectral_lag_prediction(seq),
        _regime_posterior_prediction(seq)
    ],fb)

def _v56_run_bayes(seq):
    fb=_run_hazard_prediction(seq)
    return _majority([
        _bayes_run_mixture_prediction(seq),
        _run_context_joint_prediction(seq),
        _run_survival_prediction(seq),
        _run_length_markov_prediction(seq),
        _entropy_gate_prediction(seq)
    ],fb)

def _v56_analog_multiscale(seq):
    fb=_knn_recency_prediction(seq)
    return _majority([
        _analog_knn_prediction(seq),
        _knn_recency_prediction(seq),
        _multiscale_transition_prediction(seq),
        _multiresolution_edge_prediction(seq),
        _multi_window_prediction(seq)
    ],fb)

def _v56_suffix_horizon(seq):
    fb=_suffix_prediction(seq)
    return _majority([
        _suffix_prediction(seq),
        _horizon_consensus_prediction(seq),
        _dual_horizon_prediction(seq),
        _cross_horizon_bayes_prediction(seq),
        _long_memory_bayes_prediction(seq)
    ],fb)

def _v56_stability_guard(seq):
    fb=_robust_stack_prediction(seq)
    return _majority([
        _robust_stack_prediction(seq),
        _sequential_change_prediction(seq),
        _changepoint_adaptive_prediction(seq),
        _wilson_context_prediction(seq),
        _context_entropy_prediction(seq)
    ],fb)

STRATEGY_NAMES = (
    'FOLLOW_LAST','REVERSE_LAST','ALTERNATING_PATTERN','RUN_BREAK','RUN_FOLLOW',
    'BIAS_MEAN_REVERSION','BIAS_MOMENTUM','MARKOV_TRANSITION','ANTI_RAW',
    'HIGH_ORDER_MARKOV','MARKOV_ORDER2','RUN_HAZARD','MULTI_WINDOW',
    'DECAYED_TRANSITION','REGIME_ADAPTIVE','MOTIF_WEIGHTED',
    'FLIP_STATE_MARKOV','RUN_LENGTH_MARKOV','PERIODIC_MATCH','DUAL_HORIZON',
    'ANALOG_KNN','RUN_SURVIVAL','CONTEXT_ENTROPY',
    'BAYES_CONTEXT','HORIZON_CONSENSUS','REGIME_SWITCH','LAG_ENSEMBLE',
    'REFERENCE_PATTERN_PRIOR','JS_TREND_BLEND','JS_BREAK_CALIBRATOR','JS_ULTRA_STACK',
    'VOM_CONTEXT_6','LONG_MEMORY_BAYES','RUN_PROFILE_LONG','MULTISCALE_TRANSITION',
    'CHANGEPOINT_ADAPTIVE','WILSON_CONTEXT','KNN_RECENCY','RUN_MATRIX',
    'ENTROPY_GATE','CROSS_HORIZON_BAYES',
    'DIRICHLET_VOM','SEQUENTIAL_CHANGE','MOTIF_SURVIVAL',
    'REGIME_POSTERIOR','MULTIRESOLUTION_EDGE','BAYES_RUN_MIXTURE',
    'CTW_APPROX','HIERARCHICAL_BAYES','TRANSITION_DRIFT','RUN_CONTEXT_JOINT','SPECTRAL_LAG','ROBUST_STACK',
    'SUFFIX_CONTEXT','FUSION_CORE',
    'EWMA_MARKOV_BLEND','LOCAL_GLOBAL_BAYES','MOTIF_KNN_BLEND',
    'RUN_REGIME_GUARD','DRIFT_CONSENSUS','CALIBRATED_STACK',
    'CONTEXT_DRIFT_BLEND','MOTIF_LAG_POSTERIOR','RUN_BAYES_SWITCH',
    'ANALOG_MULTISCALE','SUFFIX_HORIZON_STACK','STABILITY_GUARD_STACK'
)

def strategy_predictions(seq, board=None):
    seq=[x for x in seq if x in ('TÀI','XỈU')]
    if not seq:
        return {}
    out=dict(_v49_pure_strategy_predictions(seq,board))
    raw=_majority(list(out.values()),_markov_prediction(seq,1))
    out['FUSION_CORE']=raw
    out['ANTI_RAW']=_opp(raw)
    out.update({
        'EWMA_MARKOV_BLEND':_v55_ewma_markov(seq),
        'LOCAL_GLOBAL_BAYES':_v55_local_global_bayes(seq),
        'MOTIF_KNN_BLEND':_v55_motif_knn(seq),
        'RUN_REGIME_GUARD':_v55_run_regime(seq),
        'DRIFT_CONSENSUS':_v55_drift_consensus(seq),
        'CALIBRATED_STACK':_v55_calibrated_stack(seq),
        'CONTEXT_DRIFT_BLEND':_v56_context_drift(seq),
        'MOTIF_LAG_POSTERIOR':_v56_motif_lag(seq),
        'RUN_BAYES_SWITCH':_v56_run_bayes(seq),
        'ANALOG_MULTISCALE':_v56_analog_multiscale(seq),
        'SUFFIX_HORIZON_STACK':_v56_suffix_horizon(seq),
        'STABILITY_GUARD_STACK':_v56_stability_guard(seq),
    })
    # Keep output stable and complete.
    return {name:out.get(name,raw) for name in STRATEGY_NAMES}

def strategy_weight(n, wins):
    # Conservative beta-smoothed quality. No strategy dominates before it has evidence.
    n=max(0,int(n)); wins=max(0,min(int(wins),n))
    p=(wins+8.0)/(n+16.0)
    evidence=min(1.0,n/80.0)
    return 0.55 + evidence*max(0.0,min(1.15,(p-0.43)*2.6))

def ensemble_prediction(seq, perf=None, memory=None, board=None):
    perf=perf or {}
    preds=strategy_predictions(seq,board)
    if not preds:
        return {'prediction':'TÀI','confidence':50.0,'agreement':0.5,'strategies':{},'top':[]}
    score={'TÀI':0.0,'XỈU':0.0}
    rows=[]
    for name,pred in preds.items():
        st=perf.get(name) or {}
        n=int(st.get('n',0) or 0); wins=int(st.get('wins',0) or 0)
        w=strategy_weight(n,wins)
        score[pred]+=w
        rate=((wins+8)/(n+16)) if n>=0 else .5
        rows.append({'name':name,'prediction':pred,'n':n,'wins':wins,'rate':round(rate,4),'weight':round(w,4)})
    mem=None
    if memory:
        support=int(memory.get('support',0) or 0)
        p=float(memory.get('p_tai',0.5) or .5)
        edge=abs(p-.5)*2
        if support>=3 and edge>=.04:
            mside='TÀI' if p>=.5 else 'XỈU'
            mw=min(3.2,0.35+math.log1p(support)*0.35+edge*1.6)
            score[mside]+=mw
            mem={'prediction':mside,'weight':round(mw,3),'support':support,'p_tai':round(p,4),
                 'pattern':memory.get('pattern'),'length':memory.get('length')}
    total=score['TÀI']+score['XỈU']
    pred='TÀI' if score['TÀI']>=score['XỈU'] else 'XỈU'
    agree=(score[pred]/total) if total else .5
    # Confidence is signal strength, deliberately calibrated and capped.
    validated=[r for r in rows if r['n']>=20]
    q=sum(r['rate'] for r in validated)/len(validated) if validated else .5
    conf=50 + max(0,agree-.5)*34 + max(0,q-.5)*16
    if len(seq)<20: conf=min(conf,54)
    elif len(seq)<50: conf=min(conf,59)
    if not validated: conf=min(conf,58)
    conf=max(50.0,min(72.0,conf))
    rows.sort(key=lambda r:(r['weight'],r['n'],r['rate']),reverse=True)
    return {'prediction':pred,'confidence':round(conf,2),'agreement':round(agree,4),
            'strategies':preds,'top':rows[:12],'memory':mem,'strategy_count':len(preds)}

# ========================= ULTRA-79 ONLINE ADAPTIVE LAYER =========================
# Adds 12 meta-strategies and recent/balanced-performance weighting.
# Important: confidence remains a calibrated signal-strength score, not a guarantee.
_BASE67_NAMES = tuple(STRATEGY_NAMES)
_base67_strategy_predictions = strategy_predictions


def _u_majority(seq, fns, fallback=None):
    vals=[]
    for fn in fns:
        try:
            v=fn(seq)
        except Exception:
            v=None
        if v in ('TÀI','XỈU'):
            vals.append(v)
    if fallback is None:
        fallback=_markov_prediction(seq,2) if seq else 'TÀI'
    return _majority(vals,fallback)


def _u_run_transition(seq):
    return _u_majority(seq,[
        _run_hazard_prediction,_run_length_markov_prediction,
        lambda s:_decayed_transition_prediction(s,2),_transition_drift_prediction,
        _run_context_joint_prediction], _run_hazard_prediction(seq))


def _u_motif_context(seq):
    return _u_majority(seq,[
        _motif_weighted_prediction,_motif_survival_prediction,
        _suffix_prediction,_ctw_approx_prediction,_vom_context6_prediction],
        _motif_weighted_prediction(seq))


def _u_bayes_drift(seq):
    return _u_majority(seq,[
        _bayes_context_prediction,_hierarchical_bayes_prediction,
        _sequential_change_prediction,_transition_drift_prediction,
        _cross_horizon_bayes_prediction], _bayes_context_prediction(seq))


def _u_entropy_regime(seq):
    return _u_majority(seq,[
        _entropy_gate_prediction,_context_entropy_prediction,
        _regime_switch_prediction,_regime_posterior_prediction,
        _changepoint_adaptive_prediction], _regime_switch_prediction(seq))


def _u_multiscale_motif(seq):
    return _u_majority(seq,[
        _multiscale_transition_prediction,_multiresolution_edge_prediction,
        _motif_weighted_prediction,_lag_ensemble_prediction,_spectral_lag_prediction],
        _multiscale_transition_prediction(seq))


def _u_knn_suffix(seq):
    return _u_majority(seq,[
        _analog_knn_prediction,_knn_recency_prediction,
        _suffix_prediction,_horizon_consensus_prediction,_periodic_match_prediction],
        _knn_recency_prediction(seq))


def _u_ctw_run(seq):
    return _u_majority(seq,[
        _ctw_approx_prediction,_run_context_joint_prediction,
        _bayes_run_mixture_prediction,_run_survival_prediction,_wilson_context_prediction],
        _ctw_approx_prediction(seq))


def _u_long_short(seq):
    short=seq[-48:] if len(seq)>48 else seq
    long=seq[-320:] if len(seq)>320 else seq
    return _majority([
        _decayed_transition_prediction(short,2),
        _motif_weighted_prediction(short),
        _long_memory_bayes_prediction(long),
        _multiscale_transition_prediction(long),
        _cross_horizon_bayes_prediction(seq),
    ], _bayes_context_prediction(seq))


def _u_changepoint_guard(seq):
    return _u_majority(seq,[
        _sequential_change_prediction,_changepoint_adaptive_prediction,
        _transition_drift_prediction,_regime_switch_prediction,_robust_stack_prediction],
        _sequential_change_prediction(seq))


def _u_lag_run(seq):
    return _u_majority(seq,[
        _lag_ensemble_prediction,_spectral_lag_prediction,
        _run_hazard_prediction,_run_profile_long_prediction,_run_matrix_prediction],
        _lag_ensemble_prediction(seq))


def _u_hierarchical_stack(seq):
    return _u_majority(seq,[
        _hierarchical_bayes_prediction,_dirichlet_vom_prediction,
        _ctw_approx_prediction,_wilson_context_prediction,_robust_stack_prediction],
        _hierarchical_bayes_prediction(seq))


def _u_stable_ensemble(seq):
    experts=[
        _v56_stability_guard(seq),_u_bayes_drift(seq),_u_entropy_regime(seq),
        _u_long_short(seq),_u_motif_context(seq),_u_run_transition(seq),
        _u_hierarchical_stack(seq)
    ]
    return _majority(experts,_robust_stack_prediction(seq))


_ULTRA12 = (
    'RUN_TRANSITION_FUSION','MOTIF_CONTEXT_FUSION','BAYES_DRIFT_FUSION',
    'ENTROPY_REGIME_FUSION','MULTISCALE_MOTIF_FUSION','KNN_SUFFIX_FUSION',
    'CTW_RUN_FUSION','LONG_SHORT_CONSENSUS','CHANGEPOINT_GUARD_79',
    'LAG_RUN_FUSION','HIERARCHICAL_STACK_79','STABLE_ENSEMBLE_79'
)
STRATEGY_NAMES = tuple(dict.fromkeys(_BASE67_NAMES + _ULTRA12))


def strategy_predictions(seq, board=None):
    seq=[x for x in seq if x in ('TÀI','XỈU')]
    if not seq:
        return {}
    out=dict(_base67_strategy_predictions(seq,board))
    out.update({
        'RUN_TRANSITION_FUSION':_u_run_transition(seq),
        'MOTIF_CONTEXT_FUSION':_u_motif_context(seq),
        'BAYES_DRIFT_FUSION':_u_bayes_drift(seq),
        'ENTROPY_REGIME_FUSION':_u_entropy_regime(seq),
        'MULTISCALE_MOTIF_FUSION':_u_multiscale_motif(seq),
        'KNN_SUFFIX_FUSION':_u_knn_suffix(seq),
        'CTW_RUN_FUSION':_u_ctw_run(seq),
        'LONG_SHORT_CONSENSUS':_u_long_short(seq),
        'CHANGEPOINT_GUARD_79':_u_changepoint_guard(seq),
        'LAG_RUN_FUSION':_u_lag_run(seq),
        'HIERARCHICAL_STACK_79':_u_hierarchical_stack(seq),
        'STABLE_ENSEMBLE_79':_u_stable_ensemble(seq),
    })
    raw=_majority(list(out.values()),_markov_prediction(seq,2))
    return {name:out.get(name,raw) for name in STRATEGY_NAMES}


def _adaptive_weight(st):
    st=st or {}
    n=max(0,int(st.get('n',0) or 0)); wins=max(0,min(int(st.get('wins',0) or 0),n))
    rn=max(0,int(st.get('recent_n',0) or 0)); rw=max(0,min(int(st.get('recent_wins',0) or 0),rn))
    tn=max(0,int(st.get('tai_n',0) or 0)); tw=max(0,min(int(st.get('tai_wins',0) or 0),tn))
    xn=max(0,int(st.get('xiu_n',0) or 0)); xw=max(0,min(int(st.get('xiu_wins',0) or 0),xn))
    global_rate=(wins+10.0)/(n+20.0)
    recent_rate=(rw+5.0)/(rn+10.0) if rn else .5
    if tn and xn:
        tai_rate=(tw+4.0)/(tn+8.0); xiu_rate=(xw+4.0)/(xn+8.0)
        balanced=(tai_rate+xiu_rate)/2.0
    else:
        balanced=global_rate
    quality=.38*global_rate+.37*recent_rate+.25*balanced
    maturity=min(1.0,n/120.0)
    recent_maturity=min(1.0,rn/60.0)
    evidence=.55*maturity+.45*recent_maturity
    # Bad/unstable strategies are actually down-weighted; no early strategy can dominate.
    weight=.52 + evidence*_clamp((quality-.43)*3.0, -.30, 1.18)
    return _clamp(weight,.30,1.70), quality, balanced, recent_rate


def _regime_name(seq):
    if not seq:
        return 'COLD'
    run=_run_len(seq)
    e=_entropy(seq[-24:]) if len(seq)>=4 else 1.0
    if run>=5:
        return 'LONG-RUN'
    if e>=.96:
        return 'NOISY'
    if e<=.72:
        return 'TREND'
    if len(seq)>=12:
        flips=sum(1 for i in range(max(1,len(seq)-12),len(seq)) if seq[i]!=seq[i-1])
        if flips>=8:
            return 'ALTERNATING'
    return 'MIXED'


def ensemble_prediction(seq, perf=None, memory=None, board=None):
    perf=perf or {}
    preds=strategy_predictions(seq,board)
    if not preds:
        return {'prediction':'TÀI','confidence':50.0,'agreement':0.5,'strategies':{},'top':[],
                'strategy_count':len(STRATEGY_NAMES),'engine':'ULTRA-79'}
    score={'TÀI':0.0,'XỈU':0.0}; rows=[]
    for name,pred in preds.items():
        st=perf.get(name) or {}
        w,q,bacc,rr=_adaptive_weight(st)
        score[pred]+=w
        n=int(st.get('n',0) or 0); wins=int(st.get('wins',0) or 0)
        rows.append({'name':name,'prediction':pred,'n':n,'wins':wins,
                     'rate':round(q,4),'balanced':round(bacc,4),'recent':round(rr,4),'weight':round(w,4)})
    mem=None
    if memory:
        support=int(memory.get('support',0) or 0); p=float(memory.get('p_tai',.5) or .5)
        edge=abs(p-.5)*2
        if support>=4 and edge>=.05:
            mside='TÀI' if p>=.5 else 'XỈU'
            mw=min(2.35,.30+math.log1p(support)*.27+edge*1.35)
            score[mside]+=mw
            mem={'prediction':mside,'weight':round(mw,3),'support':support,'p_tai':round(p,4),
                 'pattern':memory.get('pattern'),'length':memory.get('length')}
    total=score['TÀI']+score['XỈU']; pred='TÀI' if score['TÀI']>=score['XỈU'] else 'XỈU'
    agree=score[pred]/total if total else .5
    validated=[r for r in rows if r['n']>=24]
    quality=sum(r['rate'] for r in validated)/len(validated) if validated else .5
    edge=abs(score['TÀI']-score['XỈU'])/max(total,1e-9)
    # Conservative calibration: many correlated strategies must not fake 90% confidence.
    conf=50 + max(0,agree-.5)*28 + max(0,quality-.5)*14 + edge*4
    if len(seq)<20: conf=min(conf,53.5)
    elif len(seq)<50: conf=min(conf,58.5)
    elif len(seq)<100: conf=min(conf,63.0)
    if not validated: conf=min(conf,57.5)
    if _regime_name(seq)=='NOISY': conf=min(conf,61.5)
    conf=_clamp(conf,50.0,69.5)
    rows.sort(key=lambda r:(r['weight'],r['recent'],r['balanced'],r['n']),reverse=True)
    return {'prediction':pred,'confidence':round(conf,2),'agreement':round(agree,4),
            'strategies':preds,'top':rows[:12],'memory':mem,'strategy_count':len(preds),
            'engine':'ULTRA-79','regime':_regime_name(seq),'edge':round(edge,4)}


# ========================= OMNI-MAX CONSOLIDATED HISTORY LAYER =========================
# Consolidates relevant sequence algorithms requested across prior versions/conversations.
# Generic sequence experts are shared. SUNWIN/Baccarat-only experts are gated by board type.
# Confidence remains a calibrated signal-strength score, not a guaranteed win probability.
_BASE79_NAMES = tuple(STRATEGY_NAMES)
_base79_strategy_predictions = strategy_predictions
_base79_ensemble_prediction = ensemble_prediction


def _mk01(v):
    return 1.0 if v == 'TÀI' else -1.0


def _generic_markov(seq, order=5, decay=False):
    if not seq:
        return 'TÀI'
    order=max(1,min(int(order),12))
    if len(seq) <= order+3:
        return _markov_prediction(seq,min(order,4))
    ctx=tuple(seq[-order:]); t=x=1.5; n=len(seq)
    for i in range(order,n):
        if tuple(seq[i-order:i]) != ctx:
            continue
        w=(0.5**((n-1-i)/180.0)) if decay else 1.0
        if seq[i]=='TÀI': t+=w
        else: x+=w
    return 'TÀI' if t>=x else 'XỈU'


def _context_2_7_prediction(seq):
    vals=[]
    for k in range(2,8):
        if len(seq)>k+4:
            vals.append(_generic_markov(seq,k,True))
    return _majority(vals,_markov_prediction(seq,2))


def _ngram_2_9_prediction(seq):
    if len(seq)<8:
        return _markov_prediction(seq,2)
    vt=vx=0.0
    n=len(seq)
    for k in range(2,min(9,n-2)+1):
        ctx=tuple(seq[-k:]); t=x=1.2; sup=0.0
        for i in range(k,n):
            if tuple(seq[i-k:i])!=ctx: continue
            age=n-1-i; w=0.5**(age/max(42.0,150.0-k*7))
            if seq[i]=='TÀI': t+=w
            else: x+=w
            sup+=w
        if sup<.8: continue
        edge=(t-x)/(t+x); wt=(.8+.08*k)*(sup/(sup+3.5))
        if edge>=0: vt+=abs(edge)*wt
        else: vx+=abs(edge)*wt
    if vt+vx<.02: return _suffix_prediction(seq)
    return 'TÀI' if vt>=vx else 'XỈU'


def _vom_2_12_prediction(seq):
    if len(seq)<10: return _markov_prediction(seq,2)
    vals=[]
    for k in range(2,min(12,len(seq)-3)+1):
        vals.append(_generic_markov(seq,k,True))
    return _majority(vals,_dirichlet_vom_prediction(seq))


def _run_lengths(seq, maxn=12):
    if not seq: return []
    out=[]; cur=seq[0]; n=1
    for v in seq[1:]:
        if v==cur: n+=1
        else:
            out.append((cur,min(n,maxn))); cur=v; n=1
    out.append((cur,min(n,maxn)))
    return out


def _cycle_template_prediction(seq, template):
    if not seq: return 'TÀI'
    runs=_run_lengths(seq)
    if not runs: return seq[-1]
    lens=[n for _,n in runs]
    side=seq[-1]; cur=lens[-1]
    L=len(template)
    # Determine phase by matching recent completed/current run lengths to cyclic template.
    best=None
    for phase in range(L):
        score=0
        for j,n in enumerate(lens[-min(len(lens),L*3):]):
            want=template[(phase-len(lens[-min(len(lens),L*3):])+1+j)%L]
            score+=abs(n-want)
        if best is None or score<best[0]: best=(score,phase)
    target=template[best[1]] if best else template[0]
    return side if cur<target else _opp(side)


def _pattern_11(seq): return _cycle_template_prediction(seq,(1,1))
def _pattern_21(seq): return _cycle_template_prediction(seq,(2,1))
def _pattern_22(seq): return _cycle_template_prediction(seq,(2,2))
def _pattern_321(seq): return _cycle_template_prediction(seq,(3,2,1))


def _block_cycle_prediction(seq):
    n=len(seq)
    if n<10: return _suffix_prediction(seq)
    for L in range(min(8,n//2),1,-1):
        a=seq[-L:]; b=seq[-2*L:-L]
        if a==b:
            # repeated block; next side follows first element of block
            return a[0]
    return _periodic_match_prediction(seq)


def _pair_state_prediction(seq):
    if len(seq)<10: return _markov_prediction(seq,2)
    states=[('S' if seq[i]==seq[i-1] else 'F') for i in range(1,len(seq))]
    if len(states)<4:return _markov_prediction(seq,2)
    key=tuple(states[-2:]); same=flip=1.0
    for i in range(2,len(states)):
        if tuple(states[i-2:i])!=key: continue
        if states[i]=='S': same+=1
        else: flip+=1
    return seq[-1] if same>=flip else _opp(seq[-1])


def _triple_state_prediction(seq):
    if len(seq)<14:return _markov_prediction(seq,3)
    key=tuple(seq[-3:]); t=x=1.0
    for i in range(3,len(seq)):
        if tuple(seq[i-3:i])!=key:continue
        if seq[i]=='TÀI':t+=1
        else:x+=1
    return 'TÀI' if t>=x else 'XỈU'


def _rle_1_10_prediction(seq):
    if len(seq)<12:return _run_hazard_prediction(seq)
    runs=_run_lengths(seq,10); side=seq[-1]; cur=min(_run_len(seq),10)
    follow=brk=1.5
    # historical chance a run of this side survives current length
    for si,n in runs[:-1]:
        if si!=side: continue
        if n>cur: follow+=1
        elif n==cur: brk+=1
    return side if follow>=brk else _opp(side)


def _autocorr_1_16_prediction(seq):
    n=len(seq)
    if n<20:return _periodic_match_prediction(seq)
    best=None
    for lag in range(1,min(16,n//3)+1):
        q=seq[-min(n,160):]
        same=sum(1 for i in range(lag,len(q)) if q[i]==q[i-lag])
        tot=max(1,len(q)-lag); rate=same/tot
        edge=abs(rate-.5)*(tot/(tot+24))
        if best is None or edge>best[0]:best=(edge,lag,rate)
    if not best:return _periodic_match_prediction(seq)
    _,lag,rate=best; candidate=seq[-lag]
    return candidate if rate>=.5 else _opp(candidate)


def _cycle_match_prediction(seq):
    if len(seq)<24:return _periodic_match_prediction(seq)
    preds=[_autocorr_1_16_prediction(seq),_spectral_lag_prediction(seq),_periodic_match_prediction(seq),_lag_ensemble_prediction(seq)]
    return _majority(preds,_periodic_match_prediction(seq))


def _multi_horizon_10_20_36_64(seq):
    vals=[]
    for w in (10,20,36,64):
        if len(seq)>=min(w,8):
            q=seq[-w:]; vals.append('TÀI' if q.count('TÀI')>=q.count('XỈU') else 'XỈU')
    vals += [_dual_horizon_prediction(seq),_horizon_consensus_prediction(seq)]
    return _majority(vals,_multi_window_prediction(seq))


def _bayes_12_24_48(seq):
    votes=[]
    for w in (12,24,48):
        q=seq[-w:]
        if len(q)<6:continue
        # Beta(3,3) posterior on side frequency.
        pt=(q.count('TÀI')+3)/(len(q)+6)
        votes.append('TÀI' if pt>=.5 else 'XỈU')
    votes += [_bayes_context_prediction(seq),_long_memory_bayes_prediction(seq)]
    return _majority(votes,_bayes_context_prediction(seq))


def _ewma_multi_prediction(seq):
    if not seq:return 'TÀI'
    votes=[]
    for alpha in (.12,.20,.32):
        e=.5
        for v in seq[-240:]:e=alpha*(1 if v=='TÀI' else 0)+(1-alpha)*e
        votes.append('TÀI' if e>=.5 else 'XỈU')
    votes.append(_decayed_transition_prediction(seq,2))
    return _majority(votes,_multi_window_prediction(seq))


def _lms_online_prediction(seq):
    # Small causal online linear learner over the latest 8 binary lags.
    if len(seq)<28:return _bayes_context_prediction(seq)
    k=8; w=[0.0]*k; b=0.0; lr=.045
    vals=[_mk01(v) for v in seq[-420:]]
    for i in range(k,len(vals)):
        x=[vals[i-j-1] for j in range(k)]; y=vals[i]
        z=b+sum(a*c for a,c in zip(w,x)); pred=max(-1,min(1,z)); err=y-pred
        step=lr/(1+.0015*i)
        b+=step*err*.25
        for j in range(k):w[j]+=step*err*x[j]/k
    x=[vals[-j-1] for j in range(k)]; z=b+sum(a*c for a,c in zip(w,x))
    return 'TÀI' if z>=0 else 'XỈU'


def _beta_posterior_prediction(seq):
    if not seq:return 'TÀI'
    t=x=4.0
    n=len(seq)
    for i,v in enumerate(seq[-320:]):
        age=min(319,n-1-i); wt=0.5**(age/120.0)
        if v=='TÀI':t+=wt
        else:x+=wt
    return 'TÀI' if t>=x else 'XỈU'


def _pattern_lock_prediction(seq):
    pats=[_suffix_prediction(seq),_motif_weighted_prediction(seq),_motif_survival_prediction(seq),_block_cycle_prediction(seq),_context_2_7_prediction(seq)]
    return _majority(pats,_motif_weighted_prediction(seq))


def _consensus_guard_prediction(seq):
    stable=[_hierarchical_bayes_prediction(seq),_ctw_approx_prediction(seq),_run_hazard_prediction(seq),_motif_weighted_prediction(seq),_multi_horizon_10_20_36_64(seq),_ewma_multi_prediction(seq)]
    return _majority(stable,_robust_stack_prediction(seq))


def _hysteresis_guard_prediction(seq):
    if not seq:return 'TÀI'
    base=_consensus_guard_prediction(seq); run=_run_len(seq)
    # Do not reverse a short stable run unless several reversal experts agree.
    rev=[_changepoint_adaptive_prediction(seq),_transition_drift_prediction(seq),_entropy_gate_prediction(seq)]
    rev_side=_opp(seq[-1]); rev_votes=sum(1 for v in rev if v==rev_side)
    if run<=3 and base==rev_side and rev_votes<2:return seq[-1]
    return base


def _error_invert_guard_prediction(seq):
    # Causal micro walk-forward: invert the current robust signal only when its recent
    # one-step behavior has been persistently poor.
    if len(seq)<45:return _robust_stack_prediction(seq)
    ok=tot=0
    start=max(24,len(seq)-14)
    for i in range(start,len(seq)):
        q=seq[:i]
        try:p=_robust_stack_prediction(q)
        except Exception:continue
        tot+=1;ok+=int(p==seq[i])
    cur=_robust_stack_prediction(seq)
    return _opp(cur) if tot>=8 and ok/tot<.36 else cur


def _three_window_confirm_prediction(seq):
    votes=[]
    for w in (12,28,60):
        q=seq[-w:]
        votes.append(_majority([_generic_markov(q,2,True),_motif_weighted_prediction(q),_run_hazard_prediction(q)],_markov_prediction(q,2)))
    return _majority(votes,_horizon_consensus_prediction(seq))


def _bcr_road_streak(seq):
    if not seq:return 'TÀI'
    r=_run_len(seq)
    if 2<=r<=3:return seq[-1]
    if 4<=r<=6:return _opp(seq[-1])
    return _run_hazard_prediction(seq)


def _bcr_dragon_break(seq):
    if not seq:return 'TÀI'
    r=_run_len(seq)
    if r>=7:return seq[-1]
    if r>=4:return _opp(seq[-1])
    return _run_survival_prediction(seq)


def _bcr_hot_zone(seq):
    if len(seq)<10:return _multi_window_prediction(seq)
    q12=seq[-12:];q24=seq[-24:]
    s12=q12.count('TÀI')-q12.count('XỈU');s24=q24.count('TÀI')-q24.count('XỈU')
    z=1.35*s12+.65*s24
    return 'TÀI' if z>=0 else 'XỈU'


def _bcr_api_road_hint(seq, meta_history=None):
    if meta_history:
        for m in reversed(meta_history[-8:]):
            s=str((m or {}).get('good_road') or '').lower()
            if not s:continue
            if ('bệt' in s or 'bet' in s or 'dính' in s or 'dinh' in s):
                if 'cái' in s or 'cai' in s or 'banker' in s:return 'TÀI'
                if 'con' in s or 'player' in s:return 'XỈU'
            if ('đảo' in s or 'dao' in s or 'xen' in s) and seq:return _opp(seq[-1])
    return _bcr_road_streak(seq)


def _valid_sun_metas(meta_history):
    out=[]
    for m in meta_history or []:
        if not isinstance(m,dict):continue
        dice=m.get('dice') or []
        total=m.get('total')
        try: total=int(total) if total is not None else (sum(map(int,dice)) if len(dice)==3 else None)
        except Exception: total=None
        try: dice=[int(x) for x in dice] if len(dice)==3 else []
        except Exception:dice=[]
        out.append({'total':total,'dice':dice})
    return out


def _sun_total_11(seq,meta_history=None):
    m=_valid_sun_metas(meta_history)
    vals=[z['total'] for z in m if isinstance(z.get('total'),int)]
    if len(vals)<8:return _multi_window_prediction(seq)
    # Weighted center around the 10/11 boundary plus transition tendency.
    q=vals[-18:]; center=sum((i+1)*v for i,v in enumerate(q))/sum(range(1,len(q)+1))
    last=q[-1]; slope=(q[-1]-q[-4])/3 if len(q)>=4 else 0
    score=(center-10.5)+.20*slope
    if last>=15:score-=.8
    elif last<=6:score+=.8
    return 'TÀI' if score>=0 else 'XỈU'


def _sun_dice_position(seq,meta_history=None):
    m=_valid_sun_metas(meta_history)
    rows=[z for z in m if len(z.get('dice') or [])==3]
    if len(rows)<12:return _markov_prediction(seq,2)
    votes=[]
    for pos in range(3):
        cur=rows[-1]['dice'][pos]; t=x=1.0
        for i in range(1,len(rows)):
            if rows[i-1]['dice'][pos]!=cur:continue
            total=rows[i].get('total')
            if not isinstance(total,int):continue
            if total>=11:t+=1
            else:x+=1
        votes.append('TÀI' if t>=x else 'XỈU')
    return _majority(votes,_markov_prediction(seq,2))


def _sun_total_band_volatility(seq,meta_history=None):
    m=_valid_sun_metas(meta_history)
    vals=[z['total'] for z in m if isinstance(z.get('total'),int)]
    if len(vals)<10:return _multi_window_prediction(seq)
    q=vals[-16:]; mean=sum(q)/len(q); var=sum((v-mean)**2 for v in q)/len(q); vol=math.sqrt(var)
    last=q[-1]
    # high volatility -> mean-reversion; low volatility -> local band persistence
    if vol>=3.0:
        return 'XỈU' if last>=12 else 'TÀI' if last<=9 else _multi_window_prediction(seq)
    recent=sum(q[-5:])/min(5,len(q))
    return 'TÀI' if recent>=10.5 else 'XỈU'


_OMNI32 = (
    'MARKOV_ORDER4_MAX','MARKOV_ORDER5','CONTEXT_2_7','NGRAM_2_9','VOM_2_12',
    'PATTERN_1_1','PATTERN_2_1','PATTERN_2_2','PATTERN_3_2_1','BLOCK_CYCLE',
    'PAIR_STATE','TRIPLE_STATE','RLE_1_10','AUTOCORR_1_16','CYCLE_MATCH',
    'MULTI_HORIZON_10_20_36_64','BAYES_12_24_48','EWMA_MULTI','LMS_ONLINE',
    'BETA_POSTERIOR','PATTERN_LOCK','CONSENSUS_GUARD','HYSTERESIS_GUARD',
    'ERROR_INVERT_GUARD','THREE_WINDOW_CONFIRM','BCR_ROAD_STREAK','BCR_DRAGON_BREAK',
    'BCR_HOT_ZONE','BCR_API_ROAD_HINT','SUN_TOTAL_11','SUN_DICE_POSITION',
    'SUN_TOTAL_BAND_VOLATILITY'
)
STRATEGY_NAMES = tuple(dict.fromkeys(_BASE79_NAMES + _OMNI32))


def strategy_predictions(seq, board=None, meta_history=None):
    seq=[x for x in seq if x in ('TÀI','XỈU')]
    if not seq:return {}
    _old=_base79_strategy_predictions(seq,board)
    out={k:_old[k] for k in _BASE79_NAMES if k in _old}
    out.update({
        'MARKOV_ORDER4_MAX':_generic_markov(seq,4,True),
        'MARKOV_ORDER5':_generic_markov(seq,5,True),
        'CONTEXT_2_7':_context_2_7_prediction(seq),
        'NGRAM_2_9':_ngram_2_9_prediction(seq),
        'VOM_2_12':_vom_2_12_prediction(seq),
        'PATTERN_1_1':_pattern_11(seq),'PATTERN_2_1':_pattern_21(seq),
        'PATTERN_2_2':_pattern_22(seq),'PATTERN_3_2_1':_pattern_321(seq),
        'BLOCK_CYCLE':_block_cycle_prediction(seq),'PAIR_STATE':_pair_state_prediction(seq),
        'TRIPLE_STATE':_triple_state_prediction(seq),'RLE_1_10':_rle_1_10_prediction(seq),
        'AUTOCORR_1_16':_autocorr_1_16_prediction(seq),'CYCLE_MATCH':_cycle_match_prediction(seq),
        'MULTI_HORIZON_10_20_36_64':_multi_horizon_10_20_36_64(seq),
        'BAYES_12_24_48':_bayes_12_24_48(seq),'EWMA_MULTI':_ewma_multi_prediction(seq),
        'LMS_ONLINE':_lms_online_prediction(seq),'BETA_POSTERIOR':_beta_posterior_prediction(seq),
        'PATTERN_LOCK':_pattern_lock_prediction(seq),'CONSENSUS_GUARD':_consensus_guard_prediction(seq),
        'HYSTERESIS_GUARD':_hysteresis_guard_prediction(seq),'ERROR_INVERT_GUARD':_error_invert_guard_prediction(seq),
        'THREE_WINDOW_CONFIRM':_three_window_confirm_prediction(seq),
    })
    b=str(board or '').lower()
    if b.startswith('baccarat:'):
        out.update({
            'BCR_ROAD_STREAK':_bcr_road_streak(seq),
            'BCR_DRAGON_BREAK':_bcr_dragon_break(seq),
            'BCR_HOT_ZONE':_bcr_hot_zone(seq),
            'BCR_API_ROAD_HINT':_bcr_api_road_hint(seq,meta_history),
        })
    elif b.startswith('sunwin:'):
        out.update({
            'SUN_TOTAL_11':_sun_total_11(seq,meta_history),
            'SUN_DICE_POSITION':_sun_dice_position(seq,meta_history),
            'SUN_TOTAL_BAND_VOLATILITY':_sun_total_band_volatility(seq,meta_history),
        })
    return out


def ensemble_prediction(seq, perf=None, memory=None, board=None, meta_history=None):
    perf=perf or {}; preds=strategy_predictions(seq,board,meta_history)
    if not preds:
        return {'prediction':'TÀI','confidence':50.0,'agreement':0.5,'strategies':{},'top':[],
                'strategy_count':0,'engine':'OMNI-MAX'}
    score={'TÀI':0.0,'XỈU':0.0}; rows=[]
    generic_set=set(_BASE79_NAMES)
    for name,pred in preds.items():
        st=perf.get(name) or {}; w,q,bacc,rr=_adaptive_weight(st)
        # New experts start slightly conservative until walk-forward evidence arrives.
        if name not in generic_set and int(st.get('n',0) or 0)<30:w*=.82
        score[pred]+=w
        n=int(st.get('n',0) or 0); wins=int(st.get('wins',0) or 0)
        rows.append({'name':name,'prediction':pred,'n':n,'wins':wins,
                     'rate':round(q,4),'balanced':round(bacc,4),'recent':round(rr,4),'weight':round(w,4)})
    mem=None
    if memory:
        support=int(memory.get('support',0) or 0); p=float(memory.get('p_tai',.5) or .5); edge_mem=abs(p-.5)*2
        if support>=4 and edge_mem>=.05:
            side='TÀI' if p>=.5 else 'XỈU'; mw=min(2.25,.28+math.log1p(support)*.26+edge_mem*1.25)
            score[side]+=mw; mem={'prediction':side,'weight':round(mw,3),'support':support,'p_tai':round(p,4),'pattern':memory.get('pattern'),'length':memory.get('length')}
    total=score['TÀI']+score['XỈU']; pred='TÀI' if score['TÀI']>=score['XỈU'] else 'XỈU'; agree=score[pred]/total if total else .5
    validated=[r for r in rows if r['n']>=24]; quality=sum(r['rate'] for r in validated)/len(validated) if validated else .5
    edge=abs(score['TÀI']-score['XỈU'])/max(total,1e-9)
    # Penalize disagreement/correlation: extra experts cannot mechanically inflate confidence.
    conf=50+max(0,agree-.5)*25+max(0,quality-.5)*13+edge*3.5
    if len(seq)<20:conf=min(conf,53.0)
    elif len(seq)<50:conf=min(conf,57.5)
    elif len(seq)<100:conf=min(conf,62.0)
    if not validated:conf=min(conf,57.0)
    regime=_regime_name(seq)
    if regime=='NOISY':conf=min(conf,60.5)
    conf=_clamp(conf,50.0,69.0)
    rows.sort(key=lambda r:(r['weight'],r['recent'],r['balanced'],r['n']),reverse=True)
    return {'prediction':pred,'confidence':round(conf,2),'agreement':round(agree,4),'strategies':preds,
            'top':rows[:14],'memory':mem,'strategy_count':len(preds),'strategy_catalog':len(STRATEGY_NAMES),
            'engine':'OMNI-MAX','regime':regime,'edge':round(edge,4)}
