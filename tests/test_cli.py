import subprocess
import sys

from claude_session_telemetry import __version__
from claude_session_telemetry.cli import DEFAULT_CLAUDE_HOME, build_parser


def test_version_flag_reports_package_version():
    result = subprocess.run(
        [sys.executable, "-m", "claude_session_telemetry.cli", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert __version__ in result.stdout


def test_claude_home_defaults_to_dot_claude():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.claude_home == DEFAULT_CLAUDE_HOME


def test_claude_home_is_overridable(tmp_path):
    parser = build_parser()
    args = parser.parse_args(["--claude-home", str(tmp_path)])
    assert args.claude_home == tmp_path
