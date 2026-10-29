import pathlib
import hashlib
import json
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build

class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'tests'/'fixture_upstream.conf').read_text(encoding='utf-8')
        # Synthetic rules stay in test code; production reads the original remote .list.
        cls.gemini='\n'.join(sorted(build.GEMINI_REQUIRED)+['DOMAIN-KEYWORD,colab']+
                             ['DOMAIN,fixture'+str(i)+'.example.com' for i in range(20)])+'\n'

    def test_all_region_filter(self):
        rx=re.compile(build.FILTER)
        for name in ('🇭🇰 香港 01','🇺🇸 美国 03','Singapore VIP','🇯🇵 日本 02','DE Frankfurt','UK London'):
            self.assertTrue(rx.fullmatch(name),name)
        for name in ('剩余流量 20G','套餐到期 2026','subscription info'):
            self.assertFalse(rx.fullmatch(name),name)

    def test_build_preserves_upstream(self):
        config,sha=build.build(self.source,self.gemini)
        self.assertEqual(len(sha),64)
        self.assertTrue(build.validate_output(config))
        self.assertIn(f'{build.BEST} = url-test,',config)
        self.assertIn(f'{build.FAILOVER} = fallback,',config)
        self.assertIn(f'FINAL,{build.SELECTOR}',config)
        self.assertIn('GEOIP,CN,DIRECT',config)
        self.assertIn('AI = select,'+build.SELECTOR,config)
        ai_line=next(line for line in config.splitlines() if line.startswith('AI ='))
        for region in ('香港节点','日本节点','美国节点'):
            self.assertIn(region,ai_line)
        self.assertIn('RULE-SET,https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/YouTube/YouTube.list,YouTube',config)
        self.assertIn('[Host]',config)
        self.assertIn('[MITM]',config)

    def test_upstream_change_refused(self):
        with self.assertRaises(build.ConfigError):
            build.build(self.source.replace('FINAL,PROXY','FINAL,DIRECT'),self.gemini)
        with self.assertRaises(build.ConfigError):
            build.build(self.source.replace('美国节点 = url-test','北美节点 = url-test'),self.gemini)

    def test_published_starter_or_full_config(self):
        actual=(ROOT/'global-auto.conf').read_text(encoding='utf-8')
        self.assertTrue(build.validate_output(actual))
        self.assertIn('\n'+build.GEMINI_RULE+'\n',actual)
        self.assertIn(f'FINAL,{build.SELECTOR}',actual)
        _,sections=build.split_sections(actual)
        active=lambda text: [line.strip() for line in text.splitlines()
                             if line.strip() and not line.lstrip().startswith(('#',';'))]
        self.assertEqual(active(sections['Proxy']),[])
        for line in active(actual):
            self.assertIsNone(re.search(r'(?i)(password|privatekey|token|auth)\s*=',line))

    def test_original_list_is_referenced_once_before_other_rules(self):
        config,_=build.build(self.source,self.gemini)
        _,sections=build.split_sections(config)
        active=[line for line in sections['Rule'].splitlines()
                if line.strip() and not line.lstrip().startswith(('#',';'))]
        self.assertEqual(active[0],build.GEMINI_RULE)
        self.assertEqual(active.count(build.GEMINI_RULE),1)
        self.assertTrue(build.GEMINI_UPSTREAM.endswith('.list'))
        self.assertFalse(any(line.startswith(('DOMAIN,fixture','DOMAIN-SUFFIX,gemini.google.com,'))
                             for line in active))

    def test_original_settings_are_preserved(self):
        config,_=build.build(self.source,self.gemini)
        _,original=build.split_sections(self.source)
        _,generated=build.split_sections(config)
        for section in ('General','Proxy','Host','URL Rewrite','MITM'):
            self.assertEqual(original[section].strip(),generated[section].strip())

    def test_rejects_unsafe_or_malformed_gemini_inputs(self):
        for extra in ('FINAL,DIRECT','DOMAIN,example.com,DIRECT','[Proxy]',
                      'RULE-SET,https://example.org/list','DOMAIN,https://example.org',
                      'DOMAIN,*.example.org','DOMAIN,example.org # comment',
                      'DOMAIN,example.org;DIRECT'):
            with self.subTest(extra=extra),self.assertRaises(build.ConfigError):
                build.build(self.source,self.gemini+'\n'+extra)
        for bad in ('<html>error</html>','',self.gemini.replace('gemini.google.com','example.com')):
            with self.subTest(bad=bad[:30]),self.assertRaises(build.ConfigError):
                build.build(self.source,bad)

    def test_gemini_deduplicates_and_preserves_order(self):
        expected=build.gemini_rules(self.gemini)
        self.assertEqual(build.gemini_rules(self.gemini+'\n'+expected[0]),expected)

    def test_rejects_bad_ai_policy_and_rule_order(self):
        config,_=build.build(self.source,self.gemini)
        bad_policy=config.replace(build.GEMINI_RULE,build.GEMINI_RULE[:-2]+'DIRECT')
        late_rule=config.replace(build.GEMINI_RULE,'FINAL,DIRECT\n'+build.GEMINI_RULE)
        missing_rule=config.replace(build.GEMINI_RULE,'# deleted')
        duplicate_rule=config.replace(build.GEMINI_RULE,build.GEMINI_RULE+'\n'+build.GEMINI_RULE)
        for bad in (bad_policy,late_rule,missing_rule,duplicate_rule):
            with self.assertRaises(build.ConfigError):
                build.validate_output(bad)

    def test_rejects_forced_us_default_or_unknown_group_member(self):
        config,_=build.build(self.source,self.gemini)
        for bad in (config.replace('AI = select,'+build.SELECTOR,'AI = select,美国节点'),
                    config.replace('AI = select,'+build.SELECTOR,
                                   'AI = select,'+build.SELECTOR+',missing-region')):
            with self.assertRaises(build.ConfigError):
                build.validate_output(bad)

    def test_node_selector_is_first_and_defaults_to_global(self):
        config,_=build.build(self.source,self.gemini)
        _,sections=build.split_sections(config)
        active=[line for line in sections['Proxy Group'].splitlines()
                if line.strip() and not line.lstrip().startswith('#')]
        self.assertTrue(active[0].startswith(build.SELECTOR+' = select,'+build.BEST+','))
        fields=active[0].split('=',1)[1].strip().split(',')
        self.assertIn('policy-select-name='+build.BEST,fields)
        self.assertIn('select=0',fields)
        for option in (build.BEST,*build.REGIONS,build.FAILOVER,build.MANUAL):
            self.assertIn(option,fields)
        self.assertNotIn('DIRECT',fields)

    def test_regional_choices_preserve_native_automatic_groups(self):
        config,_=build.build(self.source,self.gemini)
        _,original=build.split_sections(self.source)
        _,generated=build.split_sections(config)
        def definitions(text):
            return dict((line.split('=',1)[0].strip(),line.split('=',1)[1].strip())
                        for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#'))
        old=definitions(original['Proxy Group'])
        new=definitions(generated['Proxy Group'])
        samples={'香港节点':'🇭🇰 香港 01','台湾节点':'🇹🇼 台湾 01',
                 '日本节点':'🇯🇵 日本 01','新加坡节点':'🇸🇬 新加坡 01',
                 '美国节点':'🇺🇸 美国 01','韩国节点':'🇰🇷 韩国 01'}
        for region,sample in samples.items():
            self.assertEqual(old[region],new[region])
            self.assertTrue(new[region].startswith('url-test,'))
            options=dict(part.split('=',1) for part in new[region].split(',')[1:] if '=' in part)
            rx=re.compile(options['policy-regex-filter'])
            self.assertIsNotNone(rx.search(sample),region)
            self.assertIsNone(rx.search('DE Frankfurt 01'),region)

    def test_general_routes_and_service_defaults_follow_selector(self):
        config,_=build.build(self.source,self.gemini)
        _,sections=build.split_sections(config)
        for service in ('AI','YouTube','Netflix','Telegram','谷歌服务'):
            line=next(line for line in sections['Proxy Group'].splitlines()
                      if line.startswith(service+' ='))
            self.assertIn('select,'+build.SELECTOR+',',line)
            self.assertIn('policy-select-name='+build.SELECTOR,line)
        self.assertIn('GitHub/GitHub.list,'+build.SELECTOR,sections['Rule'])
        self.assertIn('Global/Global.list,'+build.SELECTOR,sections['Rule'])
        self.assertIn('GEOIP,CN,DIRECT',sections['Rule'])
        self.assertIn('FINAL,'+build.SELECTOR,sections['Rule'])
        self.assertIn('苹果服务 = select,DIRECT,',sections['Proxy Group'])
        self.assertIn(build.GEMINI_RULE,sections['Rule'])

    def test_rejects_broken_selector_region_type_and_group_cycles(self):
        config,_=build.build(self.source,self.gemini)
        for bad in (config.replace(build.BEST+',香港节点',build.BEST),
                    config.replace('美国节点 = url-test,','美国节点 = select,'),
                    config.replace(build.MANUAL+' = select,'+build.BEST,
                                   build.MANUAL+' = select,'+build.SELECTOR),
                    config.replace('FINAL,'+build.SELECTOR,'FINAL,'+build.BEST)):
            with self.assertRaises(build.ConfigError):
                build.validate_output(bad)

    def test_sync_keeps_outputs_when_either_source_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=[pathlib.Path(tmp)/name for name in ('config.conf','lock.json')]
            for path in files:
                path.write_bytes(b'last validated version')
            argv=['build.py','--output',str(files[0]),'--lock',str(files[1])]
            for responses in ([self.source,'<html>error</html>'],
                              ['[General]\ninvalid',self.gemini],
                              [self.source,OSError('network unavailable')]):
                with mock.patch.object(sys,'argv',argv), \
                     mock.patch.object(build,'fetch_text',side_effect=responses), \
                     self.assertRaises((build.ConfigError,OSError)):
                    build.main()
                for path in files:
                    self.assertEqual(path.read_bytes(),b'last validated version')

    def test_published_reference_and_source_record_match(self):
        actual=(ROOT/'global-auto.conf').read_text(encoding='utf-8')
        lock=json.loads((ROOT/'UPSTREAM.json').read_text(encoding='utf-8'))
        digest=lock['gemini']['sha256']
        self.assertRegex(digest,r'^[a-f0-9]{64}$')
        self.assertEqual(lock['gemini']['source'],build.GEMINI_UPSTREAM)
        self.assertEqual(lock['gemini']['policy'],'AI')
        self.assertGreaterEqual(lock['gemini']['rule_count'],20)
        self.assertNotIn('snapshot',lock['gemini'])
        self.assertIn('# Gemini SHA256 at build: '+digest,actual)
        self.assertIn('\n'+build.GEMINI_RULE+'\n',actual)
        self.assertFalse((ROOT/'upstream'/'Gemini_2026_Shadowrocket.list').exists())

    def test_offline_cli_is_reproducible_and_creates_no_rule_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=pathlib.Path(tmp)/'config.conf'
            lock=pathlib.Path(tmp)/'lock.json'
            source=pathlib.Path(tmp)/'input.list'
            source.write_text(self.gemini,encoding='utf-8')
            argv=['build.py','--source',str(ROOT/'tests'/'fixture_upstream.conf'),
                  '--gemini-source',str(source),'--output',str(output),'--lock',str(lock)]
            with mock.patch.object(sys,'argv',argv),mock.patch.object(build,'fetch_text') as fetch:
                build.main()
                first=[p.read_bytes() for p in (output,lock)]
                build.main()
                self.assertEqual(first,[p.read_bytes() for p in (output,lock)])
                fetch.assert_not_called()
            record=json.loads(lock.read_text(encoding='utf-8'))
            self.assertEqual(record['gemini']['sha256'],hashlib.sha256(self.gemini.encode()).hexdigest())
            self.assertEqual(set(pathlib.Path(tmp).iterdir()),{source,output,lock})

if __name__=='__main__':
    unittest.main()

