from datetime import date

from franky.catalog.parser import parse_download_code, parse_listing
from franky.db.models import EpisodeKind

LISTING = """
<form id='list' action='/index.php?all' method='post'>
<div><a href='fc/out.php?137'>07.02.10&nbsp;&nbsp;Enola Gay (самолет, сбросивший бомбу)</a>
  &nbsp;&nbsp;<small>Скачиваний:&nbsp;13185</small></div>
<div><a href='fc/out.php?-605'>=2006=&nbsp;&nbsp;The Who</a></div>
<div><a href='fc/out.php?86'>07.12.08&nbsp;&nbsp;Болан, Марк вер.2008</a></div>
<div><a href='fc/out.php?118'>06.09.09&nbsp;(ПРАЗДНИК)&nbsp;Презентация книги</a></div>
<div><a href='fc/out.php?-513'>=2005=&nbsp;(ФРАГМЕНТ)&nbsp;Трагический клоун</a></div>
<div><a href='/index.php?2011'>2011</a></div>
</form>
"""


def test_parse_listing() -> None:
    entries = {e.site_id: e for e in parse_listing(LISTING)}
    assert set(entries) == {137, -605, 86, 118, -513}

    enola = entries[137]
    assert enola.title == "Enola Gay (самолет, сбросивший бомбу)"
    assert enola.aired_on == date(2010, 2, 7)
    assert enola.aired_year == 2010
    assert enola.kind is EpisodeKind.REGULAR

    who = entries[-605]
    assert who.aired_on is None
    assert who.aired_year == 2006

    assert entries[86].title == "Болан, Марк вер.2008"
    assert entries[118].kind is EpisodeKind.SPECIAL
    assert entries[-513].kind is EpisodeKind.FRAGMENT


def test_parse_download_code() -> None:
    html = '<strong>Введите число <span class="ver1" id="nekto">3537</span></strong>'
    assert parse_download_code(html) == "3537"
    assert parse_download_code("<html></html>") is None
