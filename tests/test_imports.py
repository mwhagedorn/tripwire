from tripwire import baseline, cli, reporting, scanner


def test_modules_import():
    assert baseline.save
    assert baseline.load
    assert scanner.Scanner
    assert reporting.render_text
    assert cli.main
