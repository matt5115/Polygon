import yaml
import pathlib

def test_yaml_loads():
    cfg = yaml.safe_load(pathlib.Path("config/futures_rules.yaml").read_text())
    assert "tranches" in cfg and len(cfg["tranches"]) >= 2
