import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build

class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'tests'/'fixture_upstream.conf').read_text(encoding='utf-8')

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
        self.assertNotIn('password=',actual)

if __name__=='__main__':
    unittest.main()
