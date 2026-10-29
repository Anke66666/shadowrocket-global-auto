#!/usr/bin/env python3
"""Build Johnshall config with a direct Gemini .list reference and selectable policies."""
import argparse
import hashlib
import json
import pathlib
import re
import urllib.request

UPSTREAM = 'https://raw.githubusercontent.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/release/lazy_group.conf'
GEMINI_UPSTREAM = 'https://raw.githubusercontent.com/Anke66666/gemini-shadowrocket-rules/main/Gemini_2026_Shadowrocket.list'
GEMINI_RULE = 'RULE-SET,' + GEMINI_UPSTREAM + ',AI'
GEMINI_REQUIRED = {
    'DOMAIN-SUFFIX,gemini.google.com',
    'DOMAIN-SUFFIX,aistudio.google.com',
    'DOMAIN,generativelanguage.googleapis.com',
    'DOMAIN,cloudaicompanion.googleapis.com',
}
TEST_URL = 'http://www.gstatic.com/generate_204'
BEST = '♻️ 全球自动优选'
SELECTOR = '🚀 节点选择'
FAILOVER = '🛟 故障回退'
MANUAL = '✈️ 手动选择'
REGIONS = ('香港节点','台湾节点','新加坡节点','日本节点','美国节点','韩国节点')
FILTER = r'^(?!.*(?i:剩余|剩餘|流量|套餐|到期|过期|過期|充值|续费|續費|订阅|訂閱|官网|官網|公告|客服|工单|工單|重置|流量信息|traffic remaining|traffic used|subscription info|expire date|expiry date|website|official website)).+$'
CASE_NAMES = {
 'youtube':'YouTube','netflix':'Netflix','disney+':'Disney+','max':'Max',
 'spotify':'Spotify','telegram':'Telegram','twitter':'Twitter','facebook':'Facebook',
 'paypal':'PayPal','amazon':'Amazon','tiktok':'TikTok','ai':'AI'
}
RESERVED = {
 'DIRECT','PROXY','REJECT','REJECT-DICT','REJECT-ARRAY','REJECT-200',
 'REJECT-IMG','REJECT-TINYGIF','REJECT-VIDEO','REJECT-DROP',
 'REJECT-NO-DROP','TAILSCALE','REJECT-HTTP','REJECT-SILENT'
}
HEADERS = re.compile(r'^\[([^\]\n]+)\]\s*$', re.M)

class ConfigError(ValueError):
    pass

def gemini_rules(doc):
    """Accept only policy-free domain rules, never remote policies or directives."""
    rules = []
    for number, line in enumerate(doc.splitlines(), 1):
        item = line.strip()
        if not item or item.startswith(('#', ';')):
            continue
        fields = [part.strip() for part in item.split(',')]
        if len(fields) != 2 or fields[0] not in ('DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD'):
            raise ConfigError(f'Unexpected Gemini rule at line {number}')
        kind, value = fields
        if kind == 'DOMAIN-KEYWORD':
            valid = re.fullmatch(r'[a-z0-9][a-z0-9.-]*', value)
        else:
            valid = re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}', value)
        if not valid:
            raise ConfigError(f'Invalid Gemini domain at line {number}')
        rule = ','.join(fields)
        if rule not in rules:
            rules.append(rule)
    if len(rules) < 20 or not GEMINI_REQUIRED.issubset(rules):
        raise ConfigError('Gemini rules unexpectedly shortened or missing core endpoints')
    return rules

def split_sections(doc):
    matches = list(HEADERS.finditer(doc))
    if not matches:
        raise ConfigError('Missing config sections')
    sections = {}
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        if name in sections:
            raise ConfigError(f'Duplicate section: {name}')
        stop = matches[i+1].start() if i+1 < len(matches) else len(doc)
        sections[name] = doc[m.end():stop]
    return doc[:matches[0].start()], sections

def group_names(section):
    names = []
    for line in section.splitlines():
        item = line.strip()
        if not item or item.startswith(('#',';')):
            continue
        if '=' not in item:
            raise ConfigError('Malformed group: '+item[:100])
        names.append(item.split('=',1)[0].strip())
    return names

def validate_source(doc):
    head, sections = split_sections(doc)
    for name in ('General','Proxy','Proxy Group','Rule','Host'):
        if name not in sections:
            raise ConfigError(f'Upstream missing {name}')
    names = group_names(sections['Proxy Group'])
    for name in ('AI','Telegram','YouTube',*REGIONS):
        if name not in names:
            raise ConfigError(f'Upstream renamed group: {name}')
    active_rules = [x for x in sections['Rule'].splitlines()
                    if x.strip() and not x.lstrip().startswith(('#',';'))]
    if len(doc) < 12000 or len(active_rules) < 35:
        raise ConfigError('Upstream unexpectedly shortened')
    if 'FINAL,PROXY' not in sections['Rule']:
        raise ConfigError('Upstream FINAL changed')
    return head, sections

def build(source, gemini_source):
    gemini_rules(gemini_source)
    _, sections = validate_source(source)
    original_groups = sections['Proxy Group']
    original_names = set(group_names(original_groups))
    for name in (SELECTOR,BEST,FAILOVER,MANUAL):
        if name in original_names:
            raise ConfigError('New policy collides with upstream: '+name)
    lines = [
      '# Global all-region auto-selection, using only nodes currently visible to the client.',
      f'{SELECTOR} = select,'+','.join((BEST,*REGIONS,FAILOVER,MANUAL))+f',select=0,policy-select-name={BEST}',
      f'{BEST} = url-test,policy-regex-filter={FILTER},url={TEST_URL},interval=300,timeout=5,tolerance=80',
      f'{FAILOVER} = fallback,policy-regex-filter={FILTER},url={TEST_URL},interval=300,timeout=5',
      f'{MANUAL} = select,{BEST},{FAILOVER},policy-regex-filter={FILTER},select=0',
      '# Global groups end',
    ]
    for line in original_groups.splitlines():
        s = line.strip()
        if not s or s.startswith(('#',';')) or '=' not in s:
            lines.append(line)
            continue
        name, value = line.split('=',1)
        if value.strip().startswith('select,'):
            fields = [f.strip() for f in value.strip().split(',')]
            fields = [SELECTOR if f=='PROXY' else
                      ('policy-select-name='+SELECTOR if f=='policy-select-name=PROXY' else f)
                      for f in fields]
            lines.append(name.rstrip()+' = '+','.join(fields))
        else:
            lines.append(line)
    sections['Proxy Group'] = '\n'+'\n'.join(lines)+'\n\n'
    lookup = {n.lower():n for n in group_names(sections['Proxy Group'])}
    lookup.update(CASE_NAMES)
    updated_rules = []
    for line in sections['Rule'].splitlines():
        s = line.strip()
        if not s or s.startswith(('#',';')) or ',' not in line:
            updated_rules.append(line)
            continue
        fields = line.split(',')
        if fields[0].strip()=='FINAL' and len(fields)>=2:
            p=1
        elif len(fields)>=3 and fields[0].strip() not in ('AND','OR','NOT'):
            p=2
        else:
            updated_rules.append(line)
            continue
        policy=fields[p].strip()
        if policy=='PROXY':
            fields[p]=SELECTOR
        elif policy.lower() in lookup:
            fields[p]=lookup[policy.lower()]
        updated_rules.append(','.join(fields))
    # Reference the original .list exactly like other remote rule sets.
    # Keep it before general Google/Microsoft/global rules.
    sections['Rule']='\n# Gemini enhanced rules\n'+GEMINI_RULE+'\n'+'\n'.join(updated_rules)+'\n\n'
    sha=hashlib.sha256(source.encode('utf-8')).hexdigest()
    gemini_sha=hashlib.sha256(gemini_source.encode('utf-8')).hexdigest()
    intro=(f'# Shadowrocket Global Auto | Upstream SHA256: {sha}\n'
           '# Source: https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever\n'
           '# CC BY-SA 4.0. Derived work. No private subscription or credentials.\n'
           f'# Gemini source: {GEMINI_UPSTREAM}\n'
           f'# Gemini SHA256 at build: {gemini_sha}\n'
           '# Default proxy traffic follows the node selector; services can override it.\n'
           '# Latency measurement and failover timing depend on iOS/Shadowrocket.\n\n')
    output=intro+''.join(f'[{name}]'+text for name,text in sections.items())
    validate_output(output)
    return output,sha

def validate_output(doc):
    _, sections=split_sections(doc)
    for required in ('General','Proxy','Proxy Group','Rule','Host','MITM','URL Rewrite'):
        if required not in sections:
            raise ConfigError('Missing section '+required)
    groups=group_names(sections['Proxy Group'])
    if len(groups)!=len(set(groups)):
        raise ConfigError('Duplicate group names')
    for required in (SELECTOR,BEST,FAILOVER,MANUAL,'AI','Telegram','YouTube',*REGIONS):
        if required not in groups:
            raise ConfigError('Missing group '+required)
    if not re.search('^'+re.escape(BEST)+r'\s*=\s*url-test,',sections['Proxy Group'],re.M):
        raise ConfigError('Global url-test missing')
    if not re.search('^'+re.escape(FAILOVER)+r'\s*=\s*fallback,',sections['Proxy Group'],re.M):
        raise ConfigError('Fallback missing')
    rule_text=sections['Rule']
    active_rules = [line.strip() for line in rule_text.splitlines()
                    if line.strip() and not line.lstrip().startswith(('#', ';'))]
    references = [line for line in active_rules
                  if line.startswith('RULE-SET,'+GEMINI_UPSTREAM+',')]
    if references != [GEMINI_RULE]:
        raise ConfigError('Exactly one original Gemini .list reference must use AI')
    if active_rules[0] != GEMINI_RULE:
        raise ConfigError('Gemini rule set must precede upstream rules')
    definitions = dict(line.split('=', 1) for line in sections['Proxy Group'].splitlines()
                       if line.strip() and not line.lstrip().startswith(('#', ';')))
    definitions = {name.strip(): value.strip() for name, value in definitions.items()}
    selector_fields = [part.strip() for part in definitions[SELECTOR].split(',')]
    selector_members = [part for part in selector_fields[1:] if '=' not in part]
    if (selector_fields[0] != 'select'
            or selector_members != [BEST,*REGIONS,FAILOVER,MANUAL]
            or 'select=0' not in selector_fields
            or 'policy-select-name='+BEST not in selector_fields):
        raise ConfigError('Node selector must default to global and offer all regional groups')
    for region in REGIONS:
        if not definitions[region].startswith('url-test,'):
            raise ConfigError('Region must use automatic latency selection: '+region)
    ai_fields = [part.strip() for part in definitions['AI'].split(',')]
    ai_members = [part for part in ai_fields[1:] if '=' not in part]
    if (ai_fields[0] != 'select' or not ai_members or ai_members[0] != SELECTOR
            or '美国节点' not in ai_members or '日本节点' not in ai_members
            or 'policy-select-name='+SELECTOR not in ai_fields):
        raise ConfigError('AI must follow node selector by default and retain region overrides')
    graph = {}
    for name, value in definitions.items():
        graph[name] = []
        for member in value.split(',')[1:]:
            member = member.strip()
            if '=' not in member and member not in set(groups) | RESERVED:
                raise ConfigError(f'Unknown group member {member!r} in {name}')
            if member in definitions:
                graph[name].append(member)
    visited, visiting = set(), set()
    def check_cycle(name):
        if name in visiting:
            raise ConfigError('Cyclic policy group: '+name)
        if name in visited:
            return
        visiting.add(name)
        for child in graph[name]:
            check_cycle(child)
        visiting.remove(name)
        visited.add(name)
    for name in definitions:
        check_cycle(name)
    if 'FINAL,'+SELECTOR not in active_rules:
        raise ConfigError('FINAL must follow node selector')
    if re.search(r'^FINAL,PROXY\s*$',rule_text,re.M):
        raise ConfigError('Unchanged fallback rule')
    if 'GEOIP,CN,DIRECT' not in rule_text:
        raise ConfigError('No CN direct route')
    known=set(groups)|RESERVED
    for rule in rule_text.splitlines():
        item=rule.strip()
        if not item or item.startswith(('#',';')):
            continue
        fields=[x.strip() for x in item.split(',')]
        if fields[0]=='FINAL':
            policy=fields[1] if len(fields)>1 else ''
        elif len(fields)>=3 and fields[0] not in ('AND','OR','NOT'):
            policy=fields[2]
        else:
            continue
        if policy not in known:
            raise ConfigError('Unknown policy '+repr(policy)+' in '+item[:120])
    return True

def fetch_text(url):
    req=urllib.request.Request(url,headers={'User-Agent':'shadowrocket-global-auto-sync/1.1'})
    with urllib.request.urlopen(req,timeout=30) as response:
        if response.status!=200:
            raise ConfigError('Upstream HTTP status not 200')
        data=response.read(1024*1024+1)
        if len(data)>1024*1024:
            raise ConfigError('Upstream oversized')
        return data.decode('utf-8-sig')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',help='Optional local upstream file, for tests')
    ap.add_argument('--gemini-source',help='Optional local Gemini rules, for offline builds')
    ap.add_argument('--output',default='global-auto.conf')
    ap.add_argument('--lock',default='UPSTREAM.json')
    args=ap.parse_args()
    if args.source:
        source=pathlib.Path(args.source).read_text('utf-8')
    else:
        source=fetch_text(UPSTREAM)
    gemini_source=(pathlib.Path(args.gemini_source).read_text(encoding='utf-8')
                   if args.gemini_source else fetch_text(GEMINI_UPSTREAM))
    # Fetch and validate both inputs before touching any published output.
    output,sha=build(source, gemini_source)
    lock=json.dumps({
        'source':UPSTREAM,'sha256':sha,'license':'CC BY-SA 4.0',
        'gemini': {
            'source':GEMINI_UPSTREAM,
            'sha256':hashlib.sha256(gemini_source.encode('utf-8')).hexdigest(),
            'rule_count':len(gemini_rules(gemini_source)),
            'policy':'AI',
        },
    },ensure_ascii=False,indent=2)+'\n'
    pathlib.Path(args.output).write_text(output,encoding='utf-8',newline='\n')
    pathlib.Path(args.lock).write_text(lock,encoding='utf-8',newline='\n')
    print('Output validated:',args.output,sha)

if __name__=='__main__':
    main()

