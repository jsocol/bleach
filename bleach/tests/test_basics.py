import html5lib

from nose.tools import eq_

from bleach import Bleach, render

b = Bleach()


def test_empty():
    eq_('', b.clean(''))


def test_comments_only():
    eq_('', b.clean('<!-- this is a comment -->'))
    eq_('', b.clean('<!-- this is an open comment'))


def test_with_comments():
    eq_('Just text', b.clean('<!-- comment -->Just text'))


def test_no_html():
    eq_('no html string', b.clean('no html string'))


def test_allowed_html():
    eq_('an <strong>allowed</strong> tag',
        b.clean('an <strong>allowed</strong> tag'))
    eq_('another <em>good</em> tag',
        b.clean('another <em>good</em> tag'))


def test_bad_html():
    eq_('a <em>fixed tag</em>',
        b.clean('a <em>fixed tag'))


def test_function_arguments():
    TAGS = ['span']
    ATTRS = {'span': ['style']}

    eq_('a <span style="color: red;">test</span>',
        b.clean('a <span style="color:red">test</span>',
                     tags=TAGS, attributes=ATTRS))


def test_named_arguments():
    ATTRS = {'a': ['rel', 'href']}
    s = u'<a href="http://xx.com" rel="alternate">xx.com</a>'
    eq_('<a href="http://xx.com">xx.com</a>', b.clean(s))
    eq_(s, b.clean(s, attributes=ATTRS))


def test_disallowed_html():
    eq_('a &lt;script&gt;safe()&lt;/script&gt; test',
        b.clean('a <script>safe()</script> test'))
    eq_('a &lt;style&gt;body{}&lt;/style&gt; test',
        b.clean('a <style>body{}</style> test'))
    eq_('a safe() test',
        b.clean('a <script>safe()</script> test', strip=True))
    eq_('a body{} test',
        b.clean('a <style>body{}</style> test', strip=True))


def test_bad_href():
    eq_('<em>no link</em>',
        b.clean('<em href="fail">no link</em>'))


def test_bare_entities():
    eq_('an &amp; entity', b.clean('an & entity'))
    eq_('an &lt; entity', b.clean('an < entity'))
    eq_('tag &lt; <em>and</em> entity', b.clean('tag < <em>and</em> entity'))
    eq_('&amp;', b.clean('&amp;'))


def test_escaped_entities():
    s = u'&lt;em&gt;strong&lt;/em&gt;'
    eq_(s, b.clean(s))


def test_serializer():
    s = u'<table></table>'
    eq_(s, b.clean(s, tags=['table']))
    eq_(s, b.clean(s, tags=['table'], strip=True))
    eq_(u'test<table></table>', b.linkify(u'<table>test</table>'))
    eq_(u'<p>test</p>', b.clean(u'<p>test</p>', tags=['p']))
    eq_(u'<p>test</p>', b.clean(u'<p>test</p>', tags=['p'], strip=True))


def test_no_href_links():
    s = u'<a name="anchor">x</a>'
    eq_(s, b.linkify(s, nofollow=False))


def test_weird_strings():
    s = '</3'
    eq_(b.clean(s), '')


def test_xml_render():
    parser = html5lib.HTMLParser()
    eq_(render(parser.parseFragment(''), 'src'), '')


def test_stripping():
    eq_('a test <em>with</em> <b>html</b> tags',
        b.clean('a test <em>with</em> <b>html</b> tags', strip=True))
    eq_('a test <em>with</em>  <b>html</b> tags',
        b.clean('a test <em>with</em> <img src="http://example.com/"> '
                '<b>html</b> tags', strip=True))

    s = '<p><a href="http://example.com/">link text</a></p>'
    eq_('<p>link text</p>', b.clean(s, tags=['p'], strip=True))
    s = '<p><span>multiply <span>nested <span>text</span></span></span></p>'
    eq_('<p>multiply nested text</p>', b.clean(s, tags=['p'], strip=True))

    s = ('<p><a href="http://example.com/"><img src="http://example.com/">'
         '</a></p>')
    eq_('<p><a href="http://example.com/"></a></p>',
        b.clean(s, tags=['p','a'], strip=True))
