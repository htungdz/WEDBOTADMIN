# DEVELOPER THANHTUNG VIP · 24/7 LEARNING BACKEND + ADMIN BOT
# External HTML can be hosted anywhere. This process provides API/cache/learning.
# Run: python web_admin_bot.py

import os, re, json, time, math, html, asyncio, sqlite3, hashlib, threading
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import httpx
from learning_engine import STRATEGY_NAMES, strategy_predictions, ensemble_prediction

BASE_DIR = Path(__file__).resolve().parent
PORT = int(os.getenv('PORT','8080'))
WEB_BOT_TOKEN = os.getenv('WEB_BOT_TOKEN','').strip()
ADMIN_IDS = {int(x) for x in os.getenv('ADMIN_IDS','').replace(';',',').split(',') if x.strip().lstrip('-').isdigit()}
DB_PATH = os.getenv('DB_PATH', str(BASE_DIR/'thanhtung_learning.db'))
CONFIG_PATH = Path(os.getenv('WEB_CONFIG_PATH', str(BASE_DIR/'web_config.json')))
BOT_POLL_TIMEOUT = max(5,int(os.getenv('BOT_POLL_TIMEOUT','20')))
MAX_BACKFILL_PER_BOARD=max(80,min(800,int(os.getenv('MAX_BACKFILL_PER_BOARD','320'))))

DEFAULT_CONFIG = {
    'brand':'DEVELOPER THANHTUNG VIP',
    'sunwin_game_url':'https://web.sunwin.jetzt/?affId=Sunwin',
    'sunwin_current_api':'https://amongst-plots-called-dining.trycloudflare.com/api/tx',
    'sunwin_current_fallback':'https://kwinstore.com/sunwin/tx/9b7a587deb56a4caf8de8ffdb0c13e8d22e793ae598b66c7',
    'sunwin_history_api':'https://kwinstore.com/sunwin/tx/history/9b7a587deb56a4caf8de8ffdb0c13e8d22e793ae598b66c7',
    'bcr_api':'https://bcrsexy.onrender.com/api/baccarat',
    'updated_at':0,
}

LOCK=threading.RLock()
CONFIG={}
CACHE={
    'sun_current':{'ok':False,'data':None,'ts':0,'error':'chưa tải'},
    'sun_history':{'ok':False,'data':None,'ts':0,'error':'chưa tải'},
    'bcr':{'ok':False,'data':None,'ts':0,'error':'chưa tải'},
}
LATEST={}
LEARN_STATUS={'started':time.time(),'last_cycle':0,'last_error':'','new_rounds':0,'cycles':0}


def db():
    con=sqlite3.connect(DB_PATH,timeout=20)
    con.row_factory=sqlite3.Row
    return con


def ensure_db():
    Path(DB_PATH).parent.mkdir(parents=True,exist_ok=True)
    with db() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('PRAGMA synchronous=NORMAL')
        con.execute('PRAGMA temp_store=MEMORY')
        con.execute('PRAGMA cache_size=-12000')
        con.executescript("""
        CREATE TABLE IF NOT EXISTS rounds(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          board TEXT NOT NULL,
          external_key TEXT NOT NULL,
          result TEXT NOT NULL,
          meta_json TEXT,
          seen_at REAL NOT NULL,
          UNIQUE(board,external_key)
        );
        CREATE INDEX IF NOT EXISTS idx_rounds_board_id ON rounds(board,id);

        CREATE TABLE IF NOT EXISTS strategy_log(
          board TEXT NOT NULL,
          external_key TEXT NOT NULL,
          strategy TEXT NOT NULL,
          prediction TEXT NOT NULL,
          actual TEXT NOT NULL,
          ok INTEGER NOT NULL,
          created_at REAL NOT NULL,
          PRIMARY KEY(board,external_key,strategy)
        );
        CREATE INDEX IF NOT EXISTS idx_strategy_board_strategy ON strategy_log(board,strategy,created_at);

        CREATE TABLE IF NOT EXISTS prediction_log(
          board TEXT NOT NULL,
          external_key TEXT NOT NULL,
          prediction TEXT NOT NULL,
          confidence REAL NOT NULL,
          actual TEXT NOT NULL,
          ok INTEGER NOT NULL,
          agreement REAL,
          memory_json TEXT,
          created_at REAL NOT NULL,
          PRIMARY KEY(board,external_key)
        );
        CREATE INDEX IF NOT EXISTS idx_pred_board_time ON prediction_log(board,created_at);

        CREATE TABLE IF NOT EXISTS pattern_memory(
          board TEXT NOT NULL,
          length INTEGER NOT NULL,
          pattern TEXT NOT NULL,
          tai_count INTEGER NOT NULL DEFAULT 0,
          xiu_count INTEGER NOT NULL DEFAULT 0,
          samples INTEGER NOT NULL DEFAULT 0,
          updated_at REAL NOT NULL,
          PRIMARY KEY(board,length,pattern)
        );
        CREATE INDEX IF NOT EXISTS idx_pattern_board_samples ON pattern_memory(board,samples);

        CREATE TABLE IF NOT EXISTS current_prediction(
          board TEXT PRIMARY KEY,
          prediction TEXT NOT NULL,
          confidence REAL NOT NULL,
          agreement REAL NOT NULL,
          source_len INTEGER NOT NULL,
          details_json TEXT,
          updated_at REAL NOT NULL
        );
        """)
        con.commit()


def safe_url(v):
    v=(v or '').strip()
    p=urlparse(v)
    if p.scheme not in ('http','https') or not p.netloc:
        raise ValueError('URL phải bắt đầu bằng http:// hoặc https://')
    return v


def load_config():
    global CONFIG
    data=dict(DEFAULT_CONFIG)
    try:
        if CONFIG_PATH.exists():
            obj=json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            if isinstance(obj,dict): data.update({k:v for k,v in obj.items() if k in data})
    except Exception: pass
    with LOCK: CONFIG=data


def save_config():
    CONFIG_PATH.parent.mkdir(parents=True,exist_ok=True)
    with LOCK:
        CONFIG['updated_at']=time.time()
        tmp=CONFIG_PATH.with_suffix('.tmp')
        tmp.write_text(json.dumps(CONFIG,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.replace(CONFIG_PATH)


def public_config():
    with LOCK: return dict(CONFIG)


def cache_public(name):
    with LOCK: return dict(CACHE.get(name) or {})


def json_bytes(obj):
    return json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode('utf-8')


def unwrap(x):
    for _ in range(5):
        if isinstance(x,dict) and 'data' in x:
            x=x.get('data')
        else: break
    return x


def pick(o,keys):
    if not isinstance(o,dict): return None
    for k in keys:
        if k in o and o[k] is not None: return o[k]
    return None


def _ascii(v):
    s=str(v or '').upper()
    tr=str.maketrans('ÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ',
                     'AAAAAAAAAAAAAAAAAEEEEEEEEEEEIIIIIOOOOOOOOOOOOOOOOOUUUUUUUUUUUYYYYYD')
    return s.translate(tr)


def sun_side(v,total=None):
    s=_ascii(v)
    if 'TAI' in s or s in ('T','BIG'): return 'TÀI'
    if 'XIU' in s or s in ('X','SMALL'): return 'XỈU'
    try:
        n=float(total)
        if 3<=n<=18: return 'TÀI' if n>=11 else 'XỈU'
    except Exception: pass
    return None


def sun_item(o,i=0):
    if not isinstance(o,dict): return None
    d1=pick(o,['d1','dice1','xuc_xac_1','xx1','x1'])
    d2=pick(o,['d2','dice2','xuc_xac_2','xx2','x2'])
    d3=pick(o,['d3','dice3','xuc_xac_3','xx3','x3'])
    dice=[]
    for x in (d1,d2,d3):
        try: dice.append(int(x))
        except Exception: pass
    total=pick(o,['total','tong','sum','score'])
    try: total=int(total)
    except Exception:
        total=sum(dice) if len(dice)==3 else None
    result=sun_side(pick(o,['result','ket_qua','ketqua','tai_xiu','tx','outcome','gameResult']),total)
    sid=pick(o,['phien','session','session_id','id','round','roundId','issue','gameId'])
    if sid is None: sid=i
    if not result: return None
    return {'key':str(sid),'result':result,'meta':{'sid':str(sid),'dice':dice,'total':total}}


def normalize_sun(payload):
    x=unwrap(payload)
    arr=[]
    if isinstance(x,list): arr=x
    elif isinstance(x,dict):
        for k in ('history','results','list','items','rows'):
            if isinstance(x.get(k),list): arr=x[k];break
        if not arr: arr=[v for v in x.values() if isinstance(v,dict)]
    out=[]
    for i,o in enumerate(arr):
        z=sun_item(o,i)
        if z: out.append(z)
    seen=set();clean=[]
    for z in out:
        if z['key'] in seen: continue
        seen.add(z['key']);clean.append(z)
    def sk(z):
        m=re.findall(r'\d+',z['key'])
        return (int(m[-1]) if m else 0,z['key'])
    clean.sort(key=sk)
    return clean[-MAX_BACKFILL_PER_BOARD:]


def normalize_sun_current(payload):
    x=unwrap(payload)
    if isinstance(x,list): x=x[-1] if x else None
    z=sun_item(x or {},0)
    return [z] if z else []


def normalize_bcr(payload):
    x=unwrap(payload)
    if isinstance(x,dict):
        arr=x.get('items') or x.get('tables') or x.get('results') or []
    else: arr=x if isinstance(x,list) else []
    boards={}
    for i,it in enumerate(arr):
        if not isinstance(it,dict): continue
        table=str(it.get('table') or it.get('ban') or it.get('name') or it.get('tableName') or f'Bàn {i+1}').strip()
        results=str(it.get('result') or it.get('results') or it.get('history') or it.get('cau') or '').upper()
        results=''.join(c for c in results if c in 'BPT')
        if not results: continue
        shoe=str(it.get('shoeId') or it.get('shoe_id') or it.get('shoe') or '')
        tail=results[-MAX_BACKFILL_PER_BOARD:]
        offset=max(0,len(results)-len(tail))
        rows=[]
        for j,c in enumerate(tail):
            if c=='T': continue
            prefix=results[:offset+j+1]
            digest=hashlib.sha1((table+'|'+shoe+'|'+prefix).encode()).hexdigest()[:12]
            key=f'{shoe or "shoe"}:{offset+j+1}:{digest}'
            rows.append({'key':key,'result':'TÀI' if c=='B' else 'XỈU',
                         'meta':{'table':table,'shoe':shoe,'pos':offset+j+1,'bcr':c,
                                 'good_road':it.get('good_road') or it.get('goodRoad') or it.get('road') or ''}})
        boards['baccarat:'+table]=rows
    return boards


def load_seq(con,board,limit=1400):
    rows=con.execute('SELECT result FROM rounds WHERE board=? ORDER BY id DESC LIMIT ?',(board,limit)).fetchall()
    return [r['result'] for r in reversed(rows)]


def perf_map(con,board):
    # All-time + recent + class-balanced stats. Recent window reacts to regime changes;
    # class stats reduce one-sided strategies from dominating on imbalanced runs.
    rows=con.execute("""
        SELECT strategy,
               COUNT(*) n,
               SUM(ok) wins,
               SUM(CASE WHEN actual='TÀI' THEN 1 ELSE 0 END) tai_n,
               SUM(CASE WHEN actual='TÀI' AND ok=1 THEN 1 ELSE 0 END) tai_wins,
               SUM(CASE WHEN actual='XỈU' THEN 1 ELSE 0 END) xiu_n,
               SUM(CASE WHEN actual='XỈU' AND ok=1 THEN 1 ELSE 0 END) xiu_wins
        FROM strategy_log WHERE board=? GROUP BY strategy
    """,(board,)).fetchall()
    out={r['strategy']:{
        'n':int(r['n'] or 0),'wins':int(r['wins'] or 0),
        'tai_n':int(r['tai_n'] or 0),'tai_wins':int(r['tai_wins'] or 0),
        'xiu_n':int(r['xiu_n'] or 0),'xiu_wins':int(r['xiu_wins'] or 0),
        'recent_n':0,'recent_wins':0,
    } for r in rows}
    recent=con.execute("""
      WITH ranked AS (
        SELECT strategy,ok,
               ROW_NUMBER() OVER(PARTITION BY strategy ORDER BY created_at DESC) AS rn
        FROM strategy_log WHERE board=?
      )
      SELECT strategy,COUNT(*) recent_n,SUM(ok) recent_wins
      FROM ranked WHERE rn<=160 GROUP BY strategy
    """,(board,)).fetchall()
    for r in recent:
        st=out.setdefault(r['strategy'],{'n':0,'wins':0,'tai_n':0,'tai_wins':0,'xiu_n':0,'xiu_wins':0})
        st['recent_n']=int(r['recent_n'] or 0);st['recent_wins']=int(r['recent_wins'] or 0)
    return out


def memory_signal(con,board,seq):
    best=None
    for k in range(min(8,len(seq)),1,-1):
        pat=''.join('T' if x=='TÀI' else 'X' for x in seq[-k:])
        r=con.execute('SELECT tai_count,xiu_count,samples FROM pattern_memory WHERE board=? AND length=? AND pattern=?',(board,k,pat)).fetchone()
        if not r: continue
        n=int(r['samples'] or 0)
        if n<3: continue
        p=(int(r['tai_count'])+2)/(n+4)
        edge=abs(p-.5)
        quality=edge*min(1,n/18)
        if best is None or quality>best['quality']:
            best={'pattern':pat,'length':k,'support':n,'p_tai':p,'quality':quality}
    return best


def update_pattern_memory(con,board,seq,actual,ts):
    for k in range(2,min(8,len(seq))+1):
        pat=''.join('T' if x=='TÀI' else 'X' for x in seq[-k:])
        t=1 if actual=='TÀI' else 0;x=1-t
        con.execute('''
          INSERT INTO pattern_memory(board,length,pattern,tai_count,xiu_count,samples,updated_at)
          VALUES(?,?,?,?,?,?,?)
          ON CONFLICT(board,length,pattern) DO UPDATE SET
            tai_count=tai_count+excluded.tai_count,
            xiu_count=xiu_count+excluded.xiu_count,
            samples=samples+1,
            updated_at=excluded.updated_at
        ''',(board,k,pat,t,x,1,ts))


def create_current_prediction(con,board,seq):
    if len(seq)<6: return None
    perf=perf_map(con,board);mem=memory_signal(con,board,seq)
    e=ensemble_prediction(seq,perf=perf,memory=mem,board=board)
    d={'board':board,'prediction':e['prediction'],'confidence':e['confidence'],
       'agreement':round(e['agreement']*100,1),'source_len':len(seq),
       'strategy_count':e.get('strategy_count',len(STRATEGY_NAMES)),'memory':e.get('memory'),
       'engine':e.get('engine','ULTRA-79'),'regime':e.get('regime','MIXED'),'edge':e.get('edge',0),
       'top':e.get('top',[])[:8],'updated_at':time.time()}
    con.execute('''
      INSERT INTO current_prediction(board,prediction,confidence,agreement,source_len,details_json,updated_at)
      VALUES(?,?,?,?,?,?,?)
      ON CONFLICT(board) DO UPDATE SET prediction=excluded.prediction,confidence=excluded.confidence,
        agreement=excluded.agreement,source_len=excluded.source_len,details_json=excluded.details_json,
        updated_at=excluded.updated_at
    ''',(board,d['prediction'],d['confidence'],d['agreement'],len(seq),json.dumps(d,ensure_ascii=False,separators=(',',':')),d['updated_at']))
    with LOCK: LATEST[board]=d
    return d


def learn_rows(board,rows):
    if not rows: return 0
    now=time.time();new_count=0
    with db() as con:
        seq=load_seq(con,board)
        existing={r['external_key'] for r in con.execute('SELECT external_key FROM rounds WHERE board=?',(board,))}
        perf=perf_map(con,board)
        for item in rows:
            key=str(item.get('key'));actual=item.get('result')
            if actual not in ('TÀI','XỈU') or key in existing: continue
            if len(seq)>=12:
                mem=memory_signal(con,board,seq)
                main=ensemble_prediction(seq,perf=perf,memory=mem,board=board)
                preds=main.get('strategies') or strategy_predictions(seq,board)
                for name,pred in preds.items():
                    ok=1 if pred==actual else 0
                    con.execute('INSERT OR IGNORE INTO strategy_log(board,external_key,strategy,prediction,actual,ok,created_at) VALUES(?,?,?,?,?,?,?)',(board,key,name,pred,actual,ok,now))
                    st=perf.setdefault(name,{'n':0,'wins':0});st['n']+=1;st['wins']+=ok
                con.execute('INSERT OR IGNORE INTO prediction_log(board,external_key,prediction,confidence,actual,ok,agreement,memory_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                            (board,key,main['prediction'],float(main['confidence']),actual,1 if main['prediction']==actual else 0,float(main.get('agreement',.5))*100,
                             json.dumps(main.get('memory'),ensure_ascii=False,separators=(',',':')) if main.get('memory') else None,now))
            update_pattern_memory(con,board,seq,actual,now)
            con.execute('INSERT INTO rounds(board,external_key,result,meta_json,seen_at) VALUES(?,?,?,?,?)',(board,key,actual,json.dumps(item.get('meta') or {},ensure_ascii=False,separators=(',',':')),now))
            existing.add(key);seq.append(actual);new_count+=1
        create_current_prediction(con,board,seq);con.commit()
    return new_count


def learn_payloads(sun_history=None,sun_current=None,bcr_payload=None):
    total=0
    try:
        if sun_history is not None: total+=learn_rows('sunwin:hu',normalize_sun(sun_history))
        if sun_current is not None: total+=learn_rows('sunwin:hu',normalize_sun_current(sun_current))
        if bcr_payload is not None:
            for board,rows in normalize_bcr(bcr_payload).items(): total+=learn_rows(board,rows)
        with LOCK:
            LEARN_STATUS['last_cycle']=time.time();LEARN_STATUS['new_rounds']+=total;LEARN_STATUS['cycles']+=1;LEARN_STATUS['last_error']=''
    except Exception as e:
        with LOCK: LEARN_STATUS['last_cycle']=time.time();LEARN_STATUS['last_error']=str(e)[:240]
    return total


def load_latest_from_db():
    with db() as con:
        for r in con.execute('SELECT board,details_json FROM current_prediction'):
            try:d=json.loads(r['details_json'])
            except Exception:continue
            LATEST[r['board']]=d


def summary_payload():
    with db() as con:
        rounds=int(con.execute('SELECT COUNT(*) FROM rounds').fetchone()[0]);boards=int(con.execute('SELECT COUNT(DISTINCT board) FROM rounds').fetchone()[0])
        patterns=int(con.execute('SELECT COUNT(*) FROM pattern_memory').fetchone()[0]);mature=int(con.execute('SELECT COUNT(*) FROM pattern_memory WHERE samples>=5').fetchone()[0])
        sample=int(con.execute('SELECT COALESCE(SUM(samples),0) FROM pattern_memory').fetchone()[0]);pr=con.execute('SELECT COUNT(*) n,COALESCE(SUM(ok),0) w FROM prediction_log').fetchone()
        sn=int(pr['n'] or 0);sw=int(pr['w'] or 0);strategies=int(con.execute('SELECT COUNT(DISTINCT strategy) FROM strategy_log').fetchone()[0])
    with LOCK:st=dict(LEARN_STATUS)
    return {'ok':True,'rounds':rounds,'boards':boards,'patterns':patterns,'mature_patterns':mature,'pattern_samples':sample,
            'settled_predictions':sn,'wins':sw,'win_rate':round(sw/sn*100,2) if sn else None,'strategies':strategies,
            'engine':f'{len(STRATEGY_NAMES)} strategy ULTRA + live pattern memory','learner':st}


def board_rows_payload():
    with db() as con:
        rows=con.execute('''
          SELECT r.board,COUNT(*) rounds,
                 (SELECT COUNT(*) FROM pattern_memory p WHERE p.board=r.board) patterns,
                 (SELECT COUNT(*) FROM pattern_memory p WHERE p.board=r.board AND p.samples>=5) mature,
                 (SELECT COUNT(*) FROM prediction_log q WHERE q.board=r.board) pn,
                 (SELECT COALESCE(SUM(ok),0) FROM prediction_log q WHERE q.board=r.board) pw
          FROM rounds r GROUP BY r.board ORDER BY rounds DESC
        ''').fetchall()
    out=[]
    for r in rows:
        n=int(r['pn'] or 0);w=int(r['pw'] or 0)
        out.append({'board':r['board'],'rounds':int(r['rounds']),'patterns':int(r['patterns'] or 0),'mature':int(r['mature'] or 0),
                    'predictions':n,'wins':w,'win_rate':round(w/n*100,1) if n else None})
    return out


def top_algo_payload(board=None,limit=20):
    where='WHERE board=?' if board else '';params=[board] if board else []
    with db() as con:
        rows=con.execute(f'''SELECT strategy,COUNT(*) n,SUM(ok) wins FROM strategy_log {where}
                            GROUP BY strategy HAVING COUNT(*)>=8
                            ORDER BY (SUM(ok)+8.0)/(COUNT(*)+16.0) DESC,COUNT(*) DESC LIMIT ?''',params+[int(limit)]).fetchall()
    return [{'strategy':r['strategy'],'n':int(r['n']),'wins':int(r['wins']),'rate':round(int(r['wins'])/int(r['n'])*100,1),
             'bayes':round((int(r['wins'])+8)/(int(r['n'])+16)*100,1)} for r in rows]


def prediction_payload(board):
    with LOCK:d=dict(LATEST.get(board) or {})
    if not d:
        with db() as con:r=con.execute('SELECT details_json FROM current_prediction WHERE board=?',(board,)).fetchone()
        if r:
            try:d=json.loads(r['details_json'])
            except Exception:d={}
    if not d:return {'ok':False,'board':board,'error':'chưa đủ dữ liệu'}
    out={'ok':True,**d}
    if board.startswith('baccarat:'):
        out['prediction_bcr']='Banker' if d.get('prediction')=='TÀI' else 'Player';out['class']='B' if d.get('prediction')=='TÀI' else 'P'
    else: out['display']='TÀI' if d.get('prediction')=='TÀI' else 'XỈU'
    return out


class Handler(BaseHTTPRequestHandler):
    server_version='ThanhtungLearning/3.0-ULTRA79'
    def log_message(self,fmt,*args): return
    def send_bytes(self,code,body,ctype='application/json; charset=utf-8'):
        self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store, no-cache, must-revalidate');self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type');self.end_headers();self.wfile.write(body)
    def do_OPTIONS(self): self.send_bytes(204,b'','text/plain')
    def do_GET(self):
        u=urlparse(self.path);path=u.path.rstrip('/') or '/';qs=parse_qs(u.query)
        if path=='/':return self.send_bytes(200,json_bytes({'ok':True,'service':'DEVELOPER THANHTUNG VIP BACKEND','mode':'24/7 learner','engine':f'{len(STRATEGY_NAMES)} strategy ULTRA + pattern memory','web':'host index externally'}))
        if path=='/config':return self.send_bytes(200,json_bytes({'ok':True,**public_config()}))
        if path=='/api/sun/current':
            c=cache_public('sun_current');return self.send_bytes(200 if c.get('ok') else 503,json_bytes(c))
        if path=='/api/sun/history':
            c=cache_public('sun_history');return self.send_bytes(200 if c.get('ok') else 503,json_bytes(c))
        if path=='/api/bcr':
            c=cache_public('bcr');return self.send_bytes(200 if c.get('ok') else 503,json_bytes(c))
        if path=='/api/learning/summary':return self.send_bytes(200,json_bytes(summary_payload()))
        if path=='/api/learning/boards':return self.send_bytes(200,json_bytes({'ok':True,'boards':board_rows_payload()}))
        if path=='/api/learning/top':
            board=(qs.get('board') or [None])[0];return self.send_bytes(200,json_bytes({'ok':True,'board':board,'rows':top_algo_payload(board,30)}))
        if path=='/api/prediction/sunwin':return self.send_bytes(200,json_bytes(prediction_payload('sunwin:hu')))
        if path=='/api/prediction/bcr':
            table=(qs.get('table') or [''])[0];return self.send_bytes(200,json_bytes(prediction_payload('baccarat:'+table)))
        if path=='/api/predictions/bcr':
            with LOCK: keys=[k for k in LATEST if k.startswith('baccarat:')]
            return self.send_bytes(200,json_bytes({'ok':True,'predictions':{k:prediction_payload(k) for k in keys}}))
        if path=='/health':
            with LOCK:ls=dict(LEARN_STATUS)
            return self.send_bytes(200,json_bytes({'ok':True,'brand':CONFIG.get('brand'),'cache':{k:{'ok':v.get('ok'),'ts':v.get('ts'),'error':v.get('error')} for k,v in CACHE.items()},'learning':ls,'summary':summary_payload()}))
        return self.send_bytes(404,json_bytes({'ok':False,'error':'not found'}))


def run_http():
    httpd=ThreadingHTTPServer(('0.0.0.0',PORT),Handler);print(f'🌐 Backend :{PORT} · API only · external web supported');httpd.serve_forever()


async def fetch_json(client,url):
    r=await client.get(url,headers={'Accept':'application/json','Cache-Control':'no-cache','User-Agent':'Mozilla/5.0'},timeout=httpx.Timeout(8.0,connect=3.0));r.raise_for_status();return r.json()


async def cache_loop():
    limits=httpx.Limits(max_connections=30,max_keepalive_connections=18,keepalive_expiry=30)
    async with httpx.AsyncClient(limits=limits,follow_redirects=True) as client:
        next_hist=next_bcr=0.0
        while True:
            cfg=public_config();now=time.monotonic();sun_data=hist_data=bcr_data=None
            try:
                try:sun_data=await fetch_json(client,cfg['sunwin_current_api'])
                except Exception:sun_data=await fetch_json(client,cfg['sunwin_current_fallback'])
                with LOCK:CACHE['sun_current']={'ok':True,'data':sun_data,'ts':time.time(),'error':''}
            except Exception as e:
                with LOCK:CACHE['sun_current']={'ok':False,'data':CACHE['sun_current'].get('data'),'ts':CACHE['sun_current'].get('ts',0),'error':str(e)[:160]}
            if now>=next_hist:
                next_hist=now+5.0
                try:
                    hist_data=await fetch_json(client,cfg['sunwin_history_api']);
                    with LOCK:CACHE['sun_history']={'ok':True,'data':hist_data,'ts':time.time(),'error':''}
                except Exception as e:
                    with LOCK:CACHE['sun_history']={'ok':False,'data':CACHE['sun_history'].get('data'),'ts':CACHE['sun_history'].get('ts',0),'error':str(e)[:160]}
            if now>=next_bcr:
                next_bcr=now+2.0
                try:
                    bcr_data=await fetch_json(client,cfg['bcr_api'])
                    with LOCK:CACHE['bcr']={'ok':True,'data':bcr_data,'ts':time.time(),'error':''}
                except Exception as e:
                    with LOCK:CACHE['bcr']={'ok':False,'data':CACHE['bcr'].get('data'),'ts':CACHE['bcr'].get('ts',0),'error':str(e)[:160]}
            if sun_data is not None or hist_data is not None or bcr_data is not None:
                await asyncio.to_thread(learn_payloads,hist_data,sun_data,bcr_data)
            await asyncio.sleep(.55)


async def tg(client,method,payload):
    if not WEB_BOT_TOKEN:return None
    try:
        r=await client.post(f'https://api.telegram.org/bot{WEB_BOT_TOKEN}/{method}',json=payload,timeout=12);j=r.json();return j.get('result') if j.get('ok') else None
    except Exception:return None


def admin_keyboard():
    return {'inline_keyboard':[
        [{'text':'📊 HỌC CẦU','callback_data':'adm:stats'},{'text':'🏆 TOP THUẬT TOÁN','callback_data':'adm:algo'}],
        [{'text':'🎮 BÀN ĐÃ HỌC','callback_data':'adm:boards'},{'text':'📡 API STATUS','callback_data':'adm:api'}],
        [{'text':'🔗 LINK / API','callback_data':'adm:links'}]
    ]}


def admin_home():
    s=summary_payload();rate='—' if s['win_rate'] is None else f"{s['win_rate']}%"
    return (f'<b>⚙️ DEVELOPER THANHTUNG VIP · ADMIN</b>\n━━━━━━━━━━━━━━━━━━\n'
            f'🧠 Engine: <b>79 strategy + Live Memory</b>\n📚 Phiên đã học: <b>{s["rounds"]}</b>\n'
            f'〽️ Cầu/mẫu đã học: <b>{s["patterns"]}</b> · chín {s["mature_patterns"]}\n'
            f'🎯 Backtest causal: <b>{s["settled_predictions"]}</b> · {rate}\n🎮 Bàn: <b>{s["boards"]}</b>\n\n'
            'Backend học 24/7 kể cả khi không ai mở web.')


def api_status_text():
    with LOCK:c={k:dict(v) for k,v in CACHE.items()}
    def one(k,label):
        v=c[k];age=int(time.time()-v.get('ts',0)) if v.get('ts') else -1
        return f'{"🟢" if v.get("ok") else "🔴"} {label} · {age}s' + (f'\n└ {html.escape(str(v.get("error")))}' if not v.get('ok') and v.get('error') else '')
    return '<b>📡 API STATUS</b>\n'+one('sun_current','SUN CURRENT')+'\n'+one('sun_history','SUN HISTORY')+'\n'+one('bcr','BCR')


def stats_text():
    s=summary_payload();rate='—' if s['win_rate'] is None else f"{s['win_rate']}%";up=int(time.time()-s['learner']['started'])
    return (f'<b>📊 THỐNG KÊ HỌC NỀN 24/7</b>\n━━━━━━━━━━━━━━━━━━\n'
            f'📚 Phiên đã học: <b>{s["rounds"]}</b>\n🎮 Số bàn: <b>{s["boards"]}</b>\n〽️ Pattern unique: <b>{s["patterns"]}</b>\n'
            f'🔥 Pattern đủ ≥5 mẫu: <b>{s["mature_patterns"]}</b>\n🧩 Tổng lượt học pattern: <b>{s["pattern_samples"]}</b>\n'
            f'🧠 Strategy đang có log: <b>{s["strategies"]}/{len(STRATEGY_NAMES)}</b>\n🎯 Dự đoán walk-forward: <b>{s["settled_predictions"]}</b>\n'
            f'✅ Đúng: <b>{s["wins"]}</b> · {rate}\n♻️ Chu kỳ worker: <b>{s["learner"]["cycles"]}</b>\n⏱ Uptime: <b>{up//3600}h {(up%3600)//60}m</b>\n\n'
            '<i>% là thống kê lịch sử đã chốt, không phải bảo đảm phiên sau.</i>')


def boards_text():
    rows=board_rows_payload();lines=['<b>🎮 BÀN / CẦU ĐÃ HỌC</b>','━━━━━━━━━━━━━━━━━━']
    for r in rows[:30]:
        rate='—' if r['win_rate'] is None else f"{r['win_rate']}%";name=html.escape(r['board'].replace('baccarat:','BCR · '))
        
        with LOCK: lp=dict(LATEST.get(r['board']) or {})
        if r['board'].startswith('baccarat:'):
            pv='BANKER' if lp.get('prediction')=='TÀI' else 'PLAYER' if lp.get('prediction')=='XỈU' else '—'
        else:
            pv=lp.get('prediction') or '—'
        cf=f"{lp.get('confidence')}%" if lp.get('confidence') is not None else '—'
        lines.append(f'• <b>{name}</b>\n  {r["rounds"]} phiên · {r["patterns"]} cầu · chín {r["mature"]} · {rate}\n  NEXT: <b>{pv}</b> · {cf}')
    if not rows:lines.append('Chưa có dữ liệu.')
    return '\n'.join(lines)[:3900]


def algo_text():
    rows=top_algo_payload(None,20);lines=['<b>🏆 TOP THUẬT TOÁN ĐÃ KIỂM TRA</b>','━━━━━━━━━━━━━━━━━━']
    for i,r in enumerate(rows,1):lines.append(f'{i:02d}. <code>{r["strategy"]}</code>\n    {r["wins"]}/{r["n"]} · raw {r["rate"]}% · hiệu chỉnh {r["bayes"]}%')
    if not rows:lines.append('Chưa đủ dữ liệu.')
    lines.append('\n<i>Xếp hạng dùng Bayes smoothing để tránh model ít mẫu leo top giả.</i>');return '\n'.join(lines)[:3900]


def links_text():
    cfg=public_config()
    return (f'<b>🔗 LINK / API</b>\n━━━━━━━━━━━━━━━━━━\n<b>SUN GAME</b>\n<code>{html.escape(cfg["sunwin_game_url"])}</code>\n\n'
            f'<b>SUN CURRENT</b>\n<code>{html.escape(cfg["sunwin_current_api"])}</code>\n\n<b>SUN HISTORY</b>\n<code>{html.escape(cfg["sunwin_history_api"])}</code>\n\n'
            f'<b>BCR API</b>\n<code>{html.escape(cfg["bcr_api"])}</code>\n\n<code>/setsunlink URL</code>\n<code>/setsunapi URL</code>\n<code>/setsunhistory URL</code>\n<code>/setbcrapi URL</code>')


async def send_admin(client,chat_id,text,keyboard=True):
    p={'chat_id':chat_id,'text':text,'parse_mode':'HTML','disable_web_page_preview':True}
    if keyboard:p['reply_markup']=admin_keyboard()
    return await tg(client,'sendMessage',p)


async def handle_admin_message(client,m):
    chat_id=(m.get('chat') or {}).get('id');uid=(m.get('from') or {}).get('id');text=(m.get('text') or '').strip()
    if not chat_id or not text:return
    if uid not in ADMIN_IDS:
        if text.startswith('/start'):await send_admin(client,chat_id,'⛔ Bot quản trị riêng.',False)
        return
    parts=text.split(maxsplit=1);cmd=parts[0].split('@',1)[0].lower();arg=parts[1].strip() if len(parts)>1 else ''
    try:
        if cmd in ('/start','/menu'):out=admin_home()
        elif cmd in ('/status','/api'):out=api_status_text()
        elif cmd in ('/stats','/learn'):out=stats_text()
        elif cmd=='/boards':out=boards_text()
        elif cmd in ('/topalgo','/algo'):out=algo_text()
        elif cmd=='/links':out=links_text()
        elif cmd=='/resetlinks':
            with LOCK:CONFIG.clear();CONFIG.update(DEFAULT_CONFIG)
            save_config();out='✅ Đã khôi phục link/API mặc định.'
        else:
            key={'/setsunlink':'sunwin_game_url','/setsunapi':'sunwin_current_api','/setsunhistory':'sunwin_history_api','/setsunfallback':'sunwin_current_fallback','/setbcrapi':'bcr_api'}.get(cmd)
            if key:
                if not arg:raise ValueError('Thiếu URL.')
                arg=safe_url(arg)
                with LOCK:CONFIG[key]=arg
                save_config();out=f'✅ Đã cập nhật <b>{key}</b>\n<code>{html.escape(arg)}</code>'
            else:out=admin_home()
    except Exception as e:out='❌ '+html.escape(str(e))
    await send_admin(client,chat_id,out,True)


async def handle_callback(client,q):
    uid=(q.get('from') or {}).get('id');msg=q.get('message') or {};chat_id=(msg.get('chat') or {}).get('id')
    await tg(client,'answerCallbackQuery',{'callback_query_id':q.get('id')})
    if uid not in ADMIN_IDS or not chat_id:return
    data=q.get('data') or '';out={'adm:stats':stats_text,'adm:algo':algo_text,'adm:boards':boards_text,'adm:api':api_status_text,'adm:links':links_text}.get(data,admin_home)()
    await send_admin(client,chat_id,out,True)


async def bot_loop():
    if not WEB_BOT_TOKEN:
        print('ℹ️ WEB_BOT_TOKEN chưa có: learner/API vẫn chạy, bot quản trị tắt.')
        while True:await asyncio.sleep(3600)
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=30,max_keepalive_connections=20)) as client:
        await tg(client,'deleteWebhook',{'drop_pending_updates':False});await tg(client,'setMyName',{'name':'DEVELOPER THANHTUNG VIP ADMIN'})
        await tg(client,'setMyCommands',{'commands':[
            {'command':'start','description':'Mở bảng quản trị'},{'command':'stats','description':'Thống kê học cầu 24/7'},
            {'command':'boards','description':'Phiên/cầu đã học từng bàn'},{'command':'topalgo','description':'Top thuật toán đã kiểm tra'},
            {'command':'status','description':'Trạng thái API'},{'command':'links','description':'Xem link/API'},
            {'command':'setsunlink','description':'Đổi link game SUNWIN'},{'command':'setsunapi','description':'Đổi API current SUNWIN'},
            {'command':'setsunhistory','description':'Đổi API history SUNWIN'},{'command':'setsunfallback','description':'Đổi API fallback SUNWIN'},{'command':'setbcrapi','description':'Đổi API Baccarat'}]})
        offset=0
        while True:
            try:
                updates=await tg(client,'getUpdates',{'offset':offset,'timeout':BOT_POLL_TIMEOUT,'limit':100,'allowed_updates':['message','callback_query']}) or []
                for u in updates:
                    offset=max(offset,int(u.get('update_id',0))+1)
                    if u.get('message'):await handle_admin_message(client,u['message'])
                    elif u.get('callback_query'):await handle_callback(client,u['callback_query'])
            except asyncio.CancelledError:raise
            except Exception:await asyncio.sleep(.8)


async def main_async():
    load_config();ensure_db();load_latest_from_db();threading.Thread(target=run_http,daemon=True).start();await asyncio.gather(cache_loop(),bot_loop())


if __name__=='__main__':
    try:asyncio.run(main_async())
    except KeyboardInterrupt:pass
