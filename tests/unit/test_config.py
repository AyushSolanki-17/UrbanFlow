"""Exercise configuration boundaries before any data workloads are added."""

import json
from pathlib import Path

import pytest

from urbanflow.cli import main
from urbanflow.config import load_settings

PROFILE = """\
[local]
data_dir = "runtime"
working_data_target_gb = 10
working_data_peak_gb = 20
stack_memory_budget_gb = 8
"""


def write_profile(tmp_path: Path, content: str = PROFILE) -> Path:
    path = tmp_path / "local.toml"
    path.write_text(content)
    return path


def test_paths_are_relative_to_profile_and_check_has_no_side_effects(tmp_path, monkeypatch):
    path = write_profile(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    settings = load_settings(path)
    assert settings.data_dir == tmp_path / "runtime"
    assert not settings.data_dir.exists()


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "true", '"20"'])
def test_rejects_invalid_budgets(tmp_path, value):
    path = write_profile(
        tmp_path, PROFILE.replace("working_data_peak_gb = 20", f"working_data_peak_gb = {value}")
    )
    with pytest.raises(ValueError, match="finite positive number"):
        load_settings(path)


def test_target_cannot_exceed_peak(tmp_path):
    path = write_profile(tmp_path, PROFILE.replace("target_gb = 10", "target_gb = 21"))
    with pytest.raises(ValueError, match="must not exceed"):
        load_settings(path)


@pytest.mark.parametrize(
    "content",
    [
        PROFILE.replace("data_dir", "data_dri"),
        PROFILE.replace('data_dir = "runtime"\n', ""),
        PROFILE.replace("[local]", "[production]"),
        PROFILE + "\n[unexpected]\nvalue = 1\n",
    ],
)
def test_rejects_unknown_or_missing_settings(tmp_path, content):
    with pytest.raises(ValueError):
        load_settings(write_profile(tmp_path, content))


@pytest.mark.parametrize("value", ['""', '"   "', "123"])
def test_rejects_invalid_data_path(tmp_path, value):
    path = write_profile(tmp_path, PROFILE.replace('"runtime"', value))
    with pytest.raises(ValueError, match="non-empty path string"):
        load_settings(path)


def test_environment_can_expand_without_changing_code(tmp_path):
    path = write_profile(tmp_path, PROFILE.replace("peak_gb = 20", "peak_gb = 200"))
    assert load_settings(path).working_data_peak_gb == 200


def test_cli_reports_validated_settings(tmp_path, capsys):
    assert main(["check-config", "--config", str(write_profile(tmp_path))]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["working_data_peak_gb"] == 20
    assert output["data_dir"] == str(tmp_path / "runtime")


@pytest.mark.parametrize(
    "content", [None, "invalid TOML", PROFILE.replace("peak_gb = 20", "peak_gb = 0")]
)
def test_cli_configuration_errors_are_actionable(tmp_path, capsys, content):
    path = tmp_path / "missing.toml" if content is None else write_profile(tmp_path, content)
    with pytest.raises(SystemExit) as error:
        main(["check-config", "--config", str(path)])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert "configuration error" in output.err
    assert not output.out
