# -*- coding: utf-8 -*-
"""从 ECDICT 生成 www/books.json 与 www/roots.json（2.1 词书数据）。

用法：
  1. git clone --depth 1 https://gitee.com/nicezh/ECDICT.git tools/_ecdict
  2. py tools/build_books.py
ECDICT 使用 MIT 许可，发布时请保留 tools/_ecdict/LICENSE 的版权声明。
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, '_ecdict', 'ecdict.csv')
ROOT_SRC = os.path.join(HERE, '_ecdict', 'wordroot.txt')
OUT = os.path.join(ROOT, 'www')

if not os.path.exists(SRC):
    print('missing', SRC)
    sys.exit(1)

def clean_zh(s):
    s = (s or '').replace('\\n', '\n')
    lines = [x.strip() for x in s.split('\n') if x.strip()]
    keep = []
    for line in lines:
        if line.startswith('[网络]'):
            continue
        line = re.sub(r'^\[[^\]]{1,10}\]\s*', '', line)
        line = re.sub(r'\s+', ' ', line).strip(' ；;，,')
        if line and line not in keep:
            keep.append(line)
    out = '；'.join(keep[:3])
    return out[:90].strip('；;，, ')

def ok_word(w):
    if not w or len(w) > 40:
        return False
    if re.search(r'[\x00-\x1f]', w):
        return False
    return bool(re.search(r'[A-Za-z]', w))

def is_phrase(w):
    parts = w.split()
    return 1 < len(parts) <= 4 and all(re.fullmatch(r"[A-Za-z][A-Za-z'\-]*", p) for p in parts)

rows = {}
with open(SRC, encoding='utf-8', newline='') as f:
    for r in csv.DictReader(f):
        w = (r.get('word') or '').strip()
        if not ok_word(w):
            continue
        zh = clean_zh(r.get('translation') or '')
        if not zh:
            continue
        key = w.lower()
        tags = (r.get('tag') or '').split()
        ph = (r.get('phonetic') or '').strip()[:40]
        try:
            frq = int(r.get('frq') or 0)
        except Exception:
            frq = 0
        try:
            bnc = int(r.get('bnc') or 0)
        except Exception:
            bnc = 0
        oxford = (r.get('oxford') or '').strip()
        rec = {'w': w, 'p': ph, 'z': zh, 't': tags, 'f': frq, 'b': bnc, 'o': oxford}
        old = rows.get(key)
        if not old:
            rows[key] = rec
        else:
            # 同一个词保留信息更全的一条
            if (len(tags) > len(old['t'])) or (not old['f'] and frq):
                if len(tags) >= len(old['t']):
                    rows[key] = rec

STOP = set('''a an the and or but if of to in on at by for with from as is am are was were be been being do does did
have has had he she it they we you i me him her them us my your his its our their this that these those there here not no
yes will would can could shall should may might must than then so such very too also just only more most some any all
both each every other another'''.split())
HIGH_BOOKS = {'cet4', 'cet6', 'ky', 'ielts', 'toefl', 'gre'}

def rank(x):
    return (x['f'] if x['f'] > 0 else 999999, x['b'] if x['b'] > 0 else 999999, len(x['w']), x['w'])

def pick(pred, limit=None, skip_stop=False, min_frq=0):
    arr = [x for x in rows.values() if pred(x)]
    if skip_stop:
        arr = [x for x in arr if x['w'].lower() not in STOP]
    if min_frq:
        arr = [x for x in arr if not (0 < x['f'] < min_frq)]
    arr.sort(key=rank)
    if limit:
        arr = arr[:limit]
    return arr

BOOKS = [
    ('zk',      '中考词汇', '初级',   '中国考试', lambda x: 'zk' in x['t']),
    ('gk',      '高考词汇', '中级',   '中国考试', lambda x: 'gk' in x['t']),
    ('cet4',    '四级词汇', '中级',   '中国考试', lambda x: 'cet4' in x['t']),
    ('cet6',    '六级词汇', '中高级', '中国考试', lambda x: 'cet6' in x['t']),
    ('ky',      '考研词汇', '高级',   '中国考试', lambda x: 'ky' in x['t']),
    ('ielts',   '雅思词汇', '高级',   '国际考试', lambda x: 'ielts' in x['t']),
    ('toefl',   '托福词汇', '高级',   '国际考试', lambda x: 'toefl' in x['t']),
    ('gre',     'GRE 词汇', '高级+',  '国际考试', lambda x: 'gre' in x['t']),
    ('oxford',  '牛津核心', '基础',   '主题词表', lambda x: x['o'] in ('1', 'K')),
    ('highfreq','高频 5000', '基础',  '主题词表',
        lambda x: not is_phrase(x['w']) and ((0 < x['f'] <= 5000) or (0 < x['b'] <= 5000))),
]
# 常用词组：考试标注 / 牛津核心 / 每个组成词都常见，最多 1500 条
common = set()
for x in rows.values():
    if not is_phrase(x['w']) and ((0 < x['f'] <= 8000) or (0 < x['b'] <= 8000)):
        common.add(x['w'].lower())

# 常用词组：人工常用短语 + ECDICT 里带考试标签/牛津核心的词组
CURATED = [p.strip().lower() for p in '''
look after,look for,look forward to,look into,look up,look down on,look out,look over,look through,look up to,look at,
take after,take apart,take away,take back,take down,take off,take on,take out,take over,take up,take care of,take part in,
take place,take advantage of,take into account,take it easy,take turns,
give up,give in,give out,give away,give back,give off,give over,give rise to,give a hand,
get up,get on,get off,get in,get out,get over,get through,get along,get away,get back,get by,get down,get into,
get rid of,get in touch with,get used to,get ready,get married,get lost,
go on,go out,go off,go over,go through,go up,go down,go back,go away,go by,go for,go in for,go along with,go ahead,go wrong,
come about,come across,come along,come back,come down,come from,come in,come off,come on,come out,come over,come true,
come up,come up with,
put on,put off,put out,put up,put down,put away,put back,put forward,put up with,put into practice,put an end to,
make up,make out,make for,make sure,make sense,make use of,make friends with,make a difference,make a living,
make up for,make fun of,make a decision,make an effort,make progress,make mistakes,
keep on,keep up,keep up with,keep away,keep back,keep down,keep off,keep out,keep to,keep in touch,keep calm,
turn on,turn off,turn up,turn down,turn into,turn out,turn over,turn to,turn around,turn back,
bring up,bring about,bring back,bring down,bring in,bring out,bring forward,bring together,
break down,break up,break into,break out,break off,break through,break in,break the rules,
call on,call off,call up,call back,call for,call in,call out,
carry on,carry out,carry away,carry off,
cut down,cut off,cut out,cut up,cut in,
fall down,fall off,fall out,fall over,fall behind,fall in love with,fall asleep,
find out,figure out,fill in,fill out,fill up,
hold on,hold up,hold back,hold out,hold down,
set up,set off,set out,set aside,set down,set back,set free,set an example,
stand up,stand out,stand by,stand for,stand in,
stay up,stay away,stay in,stay out,
work out,work on,work off,work up,
write down,write off,write out,write up,
run out,run out of,run into,run away,run over,run after,run across,
pass on,pass away,pass by,pass out,pass through,
pay back,pay off,pay for,pay attention to,
pick up,pick out,pick on,
point out,point at,point to,
pull up,pull out,pull off,pull down,pull over,
push up,push out,push through,
send for,send out,send off,send up,
show up,show off,show around,show in,show out,
sit down,sit up,sit back,sit in,sit out,
sleep in,sleep over,
speak up,speak out,speak to,speak of,
start up,start out,start off,start over,
stop by,stop off,stop over,
talk about,talk to,talk with,talk over,talk into,talk out of,
think about,think of,think over,think through,think up,
throw away,throw out,throw up,throw off,
try on,try out,try for,
wait for,wait on,wait up,
wake up,warm up,wash up,watch out,watch over,
wear out,wear off,
worry about,care about,care for,depend on,rely on,focus on,insist on,believe in,belong to,listen to,
smile at,laugh at,arrive at,arrive in,agree with,agree on,apologize for,apply for,apply to,ask for,ask about,
begin with,compare with,complain about,concentrate on,congratulate on,consist of,deal with,decide on,differ from,
dream of,escape from,prepare for,protect from,provide with,react to,refer to,result in,result from,search for,
suffer from,succeed in,translate into,according to,instead of,in spite of,by way of,as a result,as well as,
in front of,in the end,on time,at least,at once,by accident,by mistake,for example,in fact,in order to,
in addition,on purpose,out of date,up to date,as soon as,so far,at first,at last,in general
'''.replace('\n', ',').split(',') if p.strip()]
CURATED = [p for p in CURATED if p]

phrase_map = {}
for p in CURATED:
    x = rows.get(p)
    if x and is_phrase(x['w']):
        phrase_map[x['w'].lower()] = x
for x in rows.values():
    if is_phrase(x['w']) and (x['t'] or x['o'] in ('1', 'K')):
        phrase_map.setdefault(x['w'].lower(), x)
order = {p: i for i, p in enumerate(CURATED)}
phrase = sorted(phrase_map.values(), key=lambda x: (order.get(x['w'].lower(), 9999), x['w']))
phrase = phrase[:600]
BOOKS.append(('phrase', '常用词组', '实用', '主题词表', None))

book_out = []
word_map = {}
for bid, name, level, cat, pred in BOOKS:
    arr = phrase if bid == 'phrase' else pick(
        pred, skip_stop=(bid in HIGH_BOOKS), min_frq=(800 if bid in ('ielts', 'toefl', 'gre') else 0))
    words = []
    for x in arr:
        w = x['w']
        words.append(w)
        if w not in word_map:
            word_map[w] = [x['p'], x['z']]
    book_out.append({'id': bid, 'name': name, 'level': level, 'category': cat,
                     'count': len(words), 'words': words})

data = {
    'source': 'ECDICT (MIT) https://github.com/skywind3000/ECDICT',
    'built': '2026-11-11',
    'books': book_out,
    'words': word_map,
}
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, 'books.json'), 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

# ---------- 词根 ----------
root_out = {}
if os.path.exists(ROOT_SRC):
    with open(ROOT_SRC, encoding='utf-8') as f:
        roots = json.load(f)
    lower_map = {w.lower(): w for w in word_map}
    for rk, info in roots.items():
        meaning = (info.get('meaning') or '')[:40]
        cls = (info.get('class') or '')[:24]
        for ex in info.get('example') or []:
            key = re.sub(r'\d+$', '', str(ex)).strip().lower()
            w = lower_map.get(key)
            if not w:
                continue
            arr = root_out.setdefault(w.lower(), [])
            item = {'r': rk, 'm': meaning}
            if cls:
                item['c'] = cls
            if all(x['r'] != rk for x in arr) and len(arr) < 4:
                arr.append(item)

with open(os.path.join(OUT, 'roots.json'), 'w', encoding='utf-8') as f:
    json.dump(root_out, f, ensure_ascii=False, separators=(',', ':'))

print('books:', [(b['id'], b['count']) for b in book_out])
print('unique words:', len(word_map))
print('roots:', len(root_out))
print('books.json: %.2f MB' % (os.path.getsize(os.path.join(OUT, 'books.json')) / 1048576))
print('roots.json: %.2f MB' % (os.path.getsize(os.path.join(OUT, 'roots.json')) / 1048576))
