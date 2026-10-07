# DEVELOPER THANHTUNG VIP · MD5 + SHA256 TELEGRAM ANALYZER
# Auto detect 32-hex MD5 / 64-hex SHA256 · HASH-64 DEBIASED
# Run: python bot_md5.py

import os
import re
import math
import time
import asyncio
import hashlib
import zlib
from collections import OrderedDict

import httpx

BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
ADMIN_IDS = {int(x) for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip().lstrip('-').isdigit()}
BOT_POLL_TIMEOUT = max(5, int(os.getenv('BOT_POLL_TIMEOUT', '20')))
BOT_NAME = 'DEVELOPER THANHTUNG VIP'
MD5_RE = re.compile(r'^[0-9a-fA-F]{32}$')
SHA256_RE = re.compile(r'^[0-9a-fA-F]{64}$')
CACHE_MAX = 16384
_CACHE = OrderedDict()
_STATS = {'started': time.time(), 'total': 0, 'md5': 0, 'sha256': 0, 'private': 0, 'group': 0}
SEM = asyncio.Semaphore(64)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def centered(v, mid, scale):
    if not scale:
        return 0.0
    return clamp((float(v) - float(mid)) / float(scale), -1.0, 1.0)


def entropy_hex(z):
    counts = [z.count(c) for c in '0123456789abcdef']
    n = len(z)
    e = 0.0
    for c in counts:
        if c:
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
    changes = sum(1 for a,b in zip(bits,bits[1:]) if a != b)
    return centered(changes/(len(bits)-1), 0.5, 0.5)


def _byte_quads(d):
    q = max(1, len(d)//4)
    out=[]
    for i in range(4):
        part=d[i*q:(i+1)*q] if i<3 else d[i*q:]
        out.append(centered(sum(part)/max(1,len(part)),127.5,90.0))
    return out


def hash_signal64(z):
    """64 symmetric/centered statistical signals for 32/64-hex hashes. No random numbers."""
    z=z.lower()
    L=len(z)
    if L not in (32,64) or not re.fullmatch(r'[0-9a-f]+',z):
        raise ValueError('hash must be 32 or 64 hexadecimal characters')
    nib=[int(c,16) for c in z]
    bs=list(bytes.fromhex(z))
    bits=[(b>>k)&1 for b in bs for k in range(7,-1,-1)]
    sig=[]
    groups=[]

    def add(v):
        sig.append(clamp(float(v),-1.0,1.0))

    # Split into four equal quarters for either MD5 (8 nibbles) or SHA256 (16 nibbles).
    q=max(1,L//4)
    quarters=[nib[i*q:(i+1)*q] if i<3 else nib[i*q:] for i in range(4)]

    # G1 · nibble distribution (8)
    for part in quarters:
        add(centered(sum(part)/max(1,len(part)),7.5,5.0))
    for part in quarters:
        add(centered(sum(x>=8 for x in part)/max(1,len(part)),0.5,0.5))
    groups.append(sig[-8:])

    # G2 · parity / transitions (8)
    for part in quarters:
        add(centered(sum((x&1)==0 for x in part)/max(1,len(part)),0.5,0.5))
    add(transition_score([x>=8 for x in nib]))
    add(transition_score([x&1 for x in nib]))
    add(transition_score(bits))
    add(centered(sum(bits)/len(bits),0.5,0.5))
    groups.append(sig[-8:])

    # G3 · shape / symmetry (8)
    half=L//2
    quarter=L//4
    add(centered(sum(nib[:half])/half - sum(nib[half:])/half,0,5.0))
    outer=nib[:quarter]+nib[-quarter:]
    inner=nib[quarter:-quarter]
    add(centered(sum(outer)/max(1,len(outer)) - sum(inner)/max(1,len(inner)),0,5.0))
    add(centered(sum(abs(a-b) for a,b in zip(nib,nib[::-1]))/L,5.3,3.5))
    # Expected unique hex symbols rises with length; normalize around empirical midpoint.
    uniq_mid=12.0 if L==32 else 15.0
    uniq_scale=4.0 if L==32 else 2.0
    add(centered(len(set(nib)),uniq_mid,uniq_scale))
    add(centered(entropy_hex(z),3.72 if L==32 else 3.86,0.35 if L==32 else 0.20))
    add(autocorr(nib,1)); add(autocorr(nib,2)); add(autocorr(nib,3))
    groups.append(sig[-8:])

    # G4 · modular / folds (8)
    total=sum(nib)
    xor=0
    for b in bs: xor ^= b
    add(centered(total%16,7.5,7.5))
    add(centered(xor%16,7.5,7.5))
    # Four 1/4-width windows, normalized by modular arithmetic.
    chunks=[z[i*q:(i+1)*q] if i<3 else z[i*q:] for i in range(4)]
    mods=(97,89,83,79)
    for ch,m in zip(chunks,mods):
        add(centered(int(ch,16)%m,(m-1)/2,(m-1)/2))
    add(centered(sum(nib[::2])/max(1,len(nib[::2])),7.5,5.0))
    add(centered(sum(nib[1::2])/max(1,len(nib[1::2])),7.5,5.0))
    groups.append(sig[-8:])

    # G5 · SHA256 derived (8)
    d=hashlib.sha256(z.encode()).digest()
    for v in _byte_quads(d): add(v)
    add(centered(sum(b.bit_count() for b in d)/(len(d)*8),0.5,0.5))
    add(autocorr(list(d),1)); add(autocorr(list(d),2)); add(transition_score([b>=128 for b in d]))
    groups.append(sig[-8:])

    # G6 · SHA3 derived (8)
    d=hashlib.sha3_256(z.encode()).digest()
    for v in _byte_quads(d): add(v)
    add(centered(sum(b.bit_count() for b in d)/(len(d)*8),0.5,0.5))
    add(autocorr(list(d),1)); add(autocorr(list(d),3)); add(transition_score([b>=128 for b in d]))
    groups.append(sig[-8:])

    # G7 · BLAKE2s derived (8)
    d=hashlib.blake2s(z.encode()).digest()
    for v in _byte_quads(d): add(v)
    add(centered(sum(b.bit_count() for b in d)/(len(d)*8),0.5,0.5))
    add(autocorr(list(d),1)); add(autocorr(list(d),4)); add(transition_score([b>=128 for b in d]))
    groups.append(sig[-8:])

    # G8 · independent checksum / positional (8)
    crc=zlib.crc32(z.encode()) & 0xffffffff
    ad=zlib.adler32(z.encode()) & 0xffffffff
    add(centered(crc%257,128,128))
    add(centered(ad%257,128,128))
    weights=[1,3,5,7,11,13,17,19]
    add(centered(sum(nib[i]*weights[i%8] for i in range(L))%251,125,125))
    add(centered(sum(nib[L-1-i]*weights[i%8] for i in range(L))%251,125,125))
    primes=[i for i in (2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61) if i<L]
    add(centered(sum(nib[i] for i in primes)/max(1,len(primes)),7.5,5.0))
    fib=[i for i in (0,1,2,3,5,8,13,21,34,55) if i<L]
    add(centered(sum(nib[i] for i in fib)/max(1,len(fib)),7.5,5.0))
    pairxor=[nib[i]^nib[i+1] for i in range(0,L-1,2)]
    add(centered(sum(pairxor)/max(1,len(pairxor)),7.5,5.0))
    lag=7 if L==32 else 13
    rotxor=[nib[i]^nib[(i+lag)%L] for i in range(L)]
    add(centered(sum(rotxor)/L,7.5,5.0))
    groups.append(sig[-8:])

    # Robust ensemble: each family gets equal weight so correlated features do not dominate.
    gs=[]
    for g in groups:
        srt=sorted(g)
        core=srt[1:-1] if len(srt)>=6 else srt
        gs.append(sum(core)/len(core))
    gs_sort=sorted(gs)
    core_groups=gs_sort[1:-1]
    raw=sum(core_groups)/len(core_groups)

    positive=sum(1 for x in sig if x>0.035)
    negative=sum(1 for x in sig if x<-0.035)
    active=positive+negative
    consensus=max(positive,negative)/active if active else .5

    # Dead-zone avoids one-sided >= .5 tie bias.
    if abs(raw)<0.007:
        tie=hashlib.blake2b(z.encode(),digest_size=1).digest()[0]&1
        raw=0.0075 if tie else -0.0075
    pred='TÀI' if raw>0 else 'XỈU'

    # Conservative calibration. This is signal strength, not true win probability.
    strength=50 + min(7.2, abs(raw)*12.5 + max(0,consensus-.5)*4.5)
    strength=clamp(strength,50.25,57.2)
    tai=strength if pred=='TÀI' else 100-strength
    xiu=100-tai
    level='KHÁ' if strength>=55.7 and consensus>=.60 else 'NHẸ'
    return {
        'prediction':pred,
        'tai_pct':round(tai,2),
        'xiu_pct':round(xiu,2),
        'strength':round(strength,2),
        'consensus':round(consensus*100,1),
        'positive':positive,
        'negative':negative,
        'active':active,
        'level':level,
        'models':64,
        'raw':raw,
        'hash_type':'MD5' if L==32 else 'SHA256',
    }


def analyze_hash(z):
    z=z.lower()
    hit=_CACHE.get(z)
    if hit is not None:
        _CACHE.move_to_end(z)
        return dict(hit)
    r=hash_signal64(z)
    _CACHE[z]=dict(r)
    if len(_CACHE)>CACHE_MAX:
        _CACHE.popitem(last=False)
    return r


def format_result(z,r):
    short=f'{z[:8]}…{z[-8:]}'
    return (
        f'<b>⚡ {BOT_NAME}</b>\n'
        f'🔐 <b>{r["hash_type"]}</b> · HASH-{r["models"]}\n'
        f'<code>{short}</code>\n'
        f'━━━━━━━━━━━━━━━━━━\n'
        f'🎯 <b>{r["prediction"]} · {r["level"]}</b>\n'
        f'⚖️ TÀI <b>{r["tai_pct"]:.2f}%</b>  •  XỈU <b>{r["xiu_pct"]:.2f}%</b>\n'
        f'🧠 Đồng thuận <b>{r["consensus"]:.1f}%</b>\n'
        f'<i>Độ nghiêng thống kê, không phải xác suất chắc thắng.</i>'
    )


async def tg(client, method, payload):
    url=f'https://api.telegram.org/bot{BOT_TOKEN}/{method}'
    try:
        r=await client.post(url,json=payload)
        j=r.json()
        return j.get('result') if j.get('ok') else None
    except Exception:
        return None


def reply_payload(chat_id,text,msg=None):
    p={'chat_id':chat_id,'text':text,'parse_mode':'HTML','disable_web_page_preview':True}
    if msg and msg.get('message_id'):
        p['reply_parameters']={'message_id':msg['message_id'],'allow_sending_without_reply':True}
    return p


def start_text():
    return (
        f'<b>⚡ {BOT_NAME}</b>\n'
        '━━━━━━━━━━━━━━━━━━\n'
        '<b>MD5 + SHA256 ANALYZER · HASH-64</b>\n\n'
        'Gửi trực tiếp <b>MD5 32 ký tự</b> hoặc <b>SHA256 64 ký tự</b>.\n'
        'Bot tự nhận loại hash và trả kết quả ngay.\n\n'
        '• Không cần lệnh phân tích\n'
        '• Hoạt động private + group\n'
        '• Group sẽ reply đúng tin nhắn chứa hash\n'
        '• Hash khác định dạng sẽ bỏ qua\n\n'
        '<i>MD5/SHA256 là hàm băm một chiều; khi không có quy tắc ánh xạ công khai, kết quả chỉ là phân tích tín hiệu thống kê.</i>'
    )


async def handle_message(client,msg):
    chat=msg.get('chat') or {}
    chat_id=chat.get('id')
    if chat_id is None:return
    ctype=chat.get('type','private')
    text=(msg.get('text') or msg.get('caption') or '').strip()
    if not text:return
    actor=(msg.get('from') or {}).get('id')

    if text.startswith('/start'):
        await tg(client,'sendMessage',reply_payload(chat_id,start_text(),msg if ctype!='private' else None));return
    if text.startswith('/help'):
        await tg(client,'sendMessage',reply_payload(chat_id,start_text(),msg if ctype!='private' else None));return
    if text.startswith('/stats') and actor in ADMIN_IDS:
        up=int(time.time()-_STATS['started'])
        out=(f'<b>📊 HASH BOT</b>\nPhân tích: <b>{_STATS["total"]}</b>\n'
             f'MD5: {_STATS["md5"]} · SHA256: {_STATS["sha256"]}\n'
             f'Private: {_STATS["private"]} · Group: {_STATS["group"]}\nUptime: {up//3600}h {(up%3600)//60}m')
        await tg(client,'sendMessage',reply_payload(chat_id,out));return

    # Auto-detect MD5 (32 hex) or SHA256 (64 hex). Ignore other ordinary messages.
    is_md5=bool(MD5_RE.fullmatch(text))
    is_sha256=bool(SHA256_RE.fullmatch(text))
    if not (is_md5 or is_sha256):
        return

    r=analyze_hash(text)
    _STATS['total']+=1
    _STATS['md5' if is_md5 else 'sha256']+=1
    _STATS['group' if ctype!='private' else 'private']+=1
    await tg(client,'sendMessage',reply_payload(chat_id,format_result(text.lower(),r),msg if ctype!='private' else None))


async def dispatch(client,upd):
    async with SEM:
        try:
            if upd.get('message'):
                await handle_message(client,upd['message'])
        except Exception:
            pass


async def main_async():
    if not BOT_TOKEN:
        raise RuntimeError('Thiếu BOT_TOKEN')
    limits=httpx.Limits(max_connections=80,max_keepalive_connections=50,keepalive_expiry=30)
    timeout=httpx.Timeout(8.0,connect=3.0,pool=2.0)
    async with httpx.AsyncClient(limits=limits,timeout=timeout) as client:
        await tg(client,'deleteWebhook',{'drop_pending_updates':False})
        await tg(client,'setMyName',{'name':BOT_NAME})
        await tg(client,'setMyShortDescription',{'short_description':'⚡ MD5 + SHA256 · HASH-64 · phản hồi nhanh'})
        await tg(client,'setMyDescription',{'description':'MD5 + SHA256 analyzer · auto detect · HASH-64 debiased · private & group.'})
        await tg(client,'setMyCommands',{'commands':[
            {'command':'start','description':'Hướng dẫn MD5 + SHA256'},
            {'command':'help','description':'Cách sử dụng'}
        ]})
        print(f'⚡ {BOT_NAME} · MD5 + SHA256 HASH-64 started')
        offset=0
        tasks=set()
        while True:
            try:
                res=await tg(client,'getUpdates',{
                    'offset':offset,'timeout':BOT_POLL_TIMEOUT,'limit':100,
                    'allowed_updates':['message']
                }) or []
                for upd in res:
                    offset=max(offset,int(upd.get('update_id',0))+1)
                    t=asyncio.create_task(dispatch(client,upd));tasks.add(t);t.add_done_callback(tasks.discard)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(.35)


def main():
    try:asyncio.run(main_async())
    except KeyboardInterrupt:pass


if __name__=='__main__':
    main()
