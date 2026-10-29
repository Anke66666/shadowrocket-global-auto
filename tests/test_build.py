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
        cls.gemini=build.GEMINI_SNAPSHOT.read_text(encoding='utf-8')

    def test_all_region_filter(self):
        rx=re.compile(build.FILTER)
        for name in ('🇭🇰 香港 01','🇺🇸 美国 03','Singapore VIP','🇯🇵 日本 02','DE Frankfurt','UK London'):
            self.assertTrue(rx.fullmatch(name),name)
        for name in ('剩余流量 20G','套餐到期 2026','subscription info'):
            self.assertFalse(rx.fullmatch(name),name)

    def test_build_preserves_upstream(self):
        config,sha=build.build(self.source)
        self.assertEqual(len(sha),64)
        self.assertTrue(build.validate_output(config))
        self.assertIn(f'{build.BEST} = url-test,',config)
        self.assertIn(f'{build.FAILOVER} = fallback,',config)
        self.assertIn(f'FINAL,{build.BEST}',config)
        self.assertIn('GEOIP,CN,DIRECT',config)
        self.assertIn('AI = select,♻️ 全球自动优选',config)
        ai_line=next(line for line in config.splitlines() if line.startswith('AI ='))
        for region in ('香港节点','日本节点','美国节点'):
            self.assertIn(region,ai_line)
        self.assertIn('RULE-SET,https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket/YouTube/YouTube.list,YouTube',config)
        self.assertIn('[Host]',config)
        self.assertIn('[MITM]',config)

    def test_upstream_change_refused(self):
        with self.assertRaises(build.ConfigError):
            build.build(self.source.replace('FINAL,PROXY','FINAL,DIRECT'))
        with self.assertRaises(build.ConfigError):
            build.build(self.source.replace('美国节点 = url-test','北美节点 = url-test'))

    def test_published_starter_or_full_config(self):
        actual=(ROOT/'global-auto.conf').read_text(encoding='utf-8')
        self.assertTrue(build.validate_output(actual))
        self.assertIn('DOMAIN-SUFFIX,gemini.google.com,AI',actual)
        self.assertIn(f'FINAL,{build.BEST}',actual)
        _,sections=build.split_sections(actual)
        active=lambda text: [line.strip() for line in text.splitlines()
                             if line.strip() and not line.lstrip().startswith(('#',';'))]
        self.assertEqual(active(sections['Proxy']),[])
        for line in active(actual):
            self.assertIsNone(re.search(r'(?i)(password|privatekey|token|auth)\s*=',line))

    def test_every_gemini_rule_is_inlined_before_upstream_rules(self):
        config,_=build.build(self.source,self.gemini)
        _,sections=build.split_sections(config)
        active=[line for line in sections['Rule'].splitlines()
                if line.strip() and not line.lstrip().startswith(('#',';'))]
        expected=[rule+',AI' for rule in build.gemini_rules(self.gemini)]
        self.assertEqual(active[:len(expected)],expected)
        self.assertIn('DOMAIN,cloudcode-pa.googleapis.com,AI',expected)
        self.assertIn('DOMAIN,optimizationguide-pa.googleapis.com,AI',expected)

    def test_gemini_rules_cover_domains_and_shared_endpoints(self):
        config,_=build.build(self.source,self.gemini)
        _,sections=build.split_sections(config)
        # Evaluate only the first domain-rule block, before any remote rules.
        rules=sections['Rule'].split(build.GEMINI_BEGIN,1)[1].split(build.GEMINI_END,1)[0]
        def route(host):
            for line in rules.splitlines():
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                kind,value,policy=line.split(',')
                if ((kind=='DOMAIN' and host==value)
                        or (kind=='DOMAIN-SUFFIX' and (host==value or host.endswith('.'+value)))
                        or (kind=='DOMAIN-KEYWORD' and value in host)):
                    return policy
        for host in ('gemini.google.com','aistudio.google.com',
                     'generativelanguage.googleapis.com','cloudaicompanion.googleapis.com',
                     'webchannel-robinfrontend-pa.googleapis.com','sub.apis.google.com'):
            self.assertEqual(route(host),'AI',host)
        self.assertIsNone(route('www.google.com'))
        self.assertIsNone(route('gemini.google.com.example.org'))

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
        bad_policy=config.replace('DOMAIN-SUFFIX,gemini.google.com,AI',
                                  'DOMAIN-SUFFIX,gemini.google.com,DIRECT')
        late_block=config.replace(build.GEMINI_BEGIN,'FINAL,DIRECT\n'+build.GEMINI_BEGIN)
        missing_block=config.replace(build.GEMINI_BEGIN,'# deleted')
        for bad in (bad_policy,late_block,missing_block):
            with self.assertRaises(build.ConfigError):
                build.validate_output(bad)

    def test_rejects_forced_us_default_or_unknown_group_member(self):
        config,_=build.build(self.source,self.gemini)
        for bad in (config.replace('AI = select,♻️ 全球自动优选','AI = select,美国节点'),
                    config.replace('AI = select,♻️ 全球自动优选',
                                   'AI = select,♻️ 全球自动优选,missing-region')):
            with self.assertRaises(build.ConfigError):
                build.validate_output(bad)

    def test_sync_keeps_outputs_when_either_source_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=[pathlib.Path(tmp)/name for name in ('config.conf','lock.json','gemini.list')]
            for path in files:
                path.write_bytes(b'last validated version')
            argv=['build.py','--output',str(files[0]),'--lock',str(files[1]),
                  '--gemini-snapshot',str(files[2])]
            for responses in ([self.source,'<html>error</html>'],
                              ['[General]\ninvalid',self.gemini],
                              [self.source,OSError('network unavailable')]):
                with mock.patch.object(sys,'argv',argv), \
                     mock.patch.object(build,'fetch_text',side_effect=responses), \
                     self.assertRaises((build.ConfigError,OSError)):
                    build.main()
                for path in files:
                    self.assertEqual(path.read_bytes(),b'last validated version')

    def test_published_snapshot_and_lock_match_config(self):
        actual=(ROOT/'global-auto.conf').read_text(encoding='utf-8')
        lock=json.loads((ROOT/'UPSTREAM.json').read_text(encoding='utf-8'))
        digest=hashlib.sha256(self.gemini.encode('utf-8')).hexdigest()
        self.assertEqual(lock['gemini']['sha256'],digest)
        self.assertEqual(lock['gemini']['source'],build.GEMINI_UPSTREAM)
        self.assertEqual(lock['gemini']['rule_count'],len(build.gemini_rules(self.gemini)))
        self.assertIn('# Gemini SHA256: '+digest,actual)
        for rule in build.gemini_rules(self.gemini):
            self.assertIn('\n'+rule+',AI\n',actual)

    def test_offline_cli_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=pathlib.Path(tmp)/'config.conf'
            lock=pathlib.Path(tmp)/'lock.json'
            snapshot=pathlib.Path(tmp)/'snapshot.list'
            argv=['build.py','--source',str(ROOT/'tests'/'fixture_upstream.conf'),
                  '--gemini-source',str(build.GEMINI_SNAPSHOT),
                  '--output',str(output),'--lock',str(lock),'--gemini-snapshot',str(snapshot)]
            with mock.patch.object(sys,'argv',argv),mock.patch.object(build,'fetch_text') as fetch:
                build.main()
                first=[p.read_bytes() for p in (output,lock,snapshot)]
                build.main()
                self.assertEqual(first,[p.read_bytes() for p in (output,lock,snapshot)])
                fetch.assert_not_called()

if __name__=='__main__':
    unittest.main()

