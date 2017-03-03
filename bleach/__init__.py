# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import logging
import re

import html5lib
from html5lib.filters import sanitizer
from html5lib.filters.sanitizer import allowed_protocols
from html5lib.serializer import HTMLSerializer

from bleach import callbacks as linkify_callbacks
from bleach.encoding import force_unicode
from bleach.sanitizer import BleachSanitizerFilter
from bleach.version import __version__, VERSION # flake8: noqa

__all__ = ['Cleaner', 'clean', 'linkify']

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

ALLOWED_TAGS = [
    'a',
    'abbr',
    'acronym',
    'b',
    'blockquote',
    'code',
    'em',
    'i',
    'li',
    'ol',
    'strong',
    'ul',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'abbr': ['title'],
    'acronym': ['title'],
}

ALLOWED_STYLES = []

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

TLDS = """ac ad ae aero af ag ai al am an ao aq ar arpa as asia at au aw ax az
       ba bb bd be bf bg bh bi biz bj bm bn bo br bs bt bv bw by bz ca cat
       cc cd cf cg ch ci ck cl cm cn co com coop cr cu cv cx cy cz de dj dk
       dm do dz ec edu ee eg er es et eu fi fj fk fm fo fr ga gb gd ge gf gg
       gh gi gl gm gn gov gp gq gr gs gt gu gw gy hk hm hn hr ht hu id ie il
       im in info int io iq ir is it je jm jo jobs jp ke kg kh ki km kn kp
       kr kw ky kz la lb lc li lk lr ls lt lu lv ly ma mc md me mg mh mil mk
       ml mm mn mo mobi mp mq mr ms mt mu museum mv mw mx my mz na name nc ne
       net nf ng ni nl no np nr nu nz om org pa pe pf pg ph pk pl pm pn post
       pr pro ps pt pw py qa re ro rs ru rw sa sb sc sd se sg sh si sj sk sl
       sm sn so sr ss st su sv sx sy sz tc td tel tf tg th tj tk tl tm tn to
       tp tr travel tt tv tw tz ua ug uk us uy uz va vc ve vg vi vn vu wf ws
       xn xxx ye yt yu za zm zw""".split()

# Make sure that .com doesn't get matched by .co first
TLDS.reverse()

url_re = re.compile(
    r"""\(*  # Match any opening parentheses.
    \b(?<![@.])(?:(?:{0}):/{{0,3}}(?:(?:\w+:)?\w+@)?)?  # http://
    ([\w-]+\.)+(?:{1})(?:\:[0-9]+)?(?!\.\w)\b   # xx.yy.tld(:##)?
    (?:[/?][^\s\{{\}}\|\\\^\[\]`<>"]*)?
        # /path/zz (excluding "unsafe" chars from RFC 1738,
        # except for # and ~, which happen in practice)
    """.format('|'.join(allowed_protocols), '|'.join(TLDS)),
    re.IGNORECASE | re.VERBOSE | re.UNICODE)

proto_re = re.compile(r'^[\w-]+:/{0,3}', re.IGNORECASE)

punct_re = re.compile(r'([\.,]+)$')

email_re = re.compile(
    r"""(?<!//)
    (([-!#$%&'*+/=?^_`{0!s}|~0-9A-Z]+
        (\.[-!#$%&'*+/=?^_`{1!s}|~0-9A-Z]+)*  # dot-atom
    |^"([\001-\010\013\014\016-\037!#-\[\]-\177]
        |\\[\001-011\013\014\016-\177])*"  # quoted-string
    )@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6})  # domain
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE)

ETREE_TAG = lambda x: "".join(['{http://www.w3.org/1999/xhtml}', x])
# a simple routine that returns the tag name with the namespace prefix
# as returned by etree's Element.tag attribute

DEFAULT_CALLBACKS = [linkify_callbacks.nofollow]


class Cleaner(object):
    """Cleaner for cleaning HTML fragments of malicious content

    This cleaner is a security-focused function whose sole purpose is to remove
    malicious content from a string such that it can be displayed as content in
    a web page.

    This cleaner is not designed to use to transform content to be used in
    non-web-page contexts.

    To use::

        from bleach import Cleaner

        cleaner = Cleaner()

        for text in all_the_yucky_things:
            sanitized = cleaner.clean(text)

    """

    def __init__(self, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES,
                 styles=ALLOWED_STYLES, protocols=ALLOWED_PROTOCOLS, strip=False,
                 strip_comments=True, filters=None):
        """Initializes a Cleaner

        :arg tags: whitelist of allowed tags; defaults to
            ``bleach.ALLOWED_TAGS``

        :arg attributes: whitelist of allowed attributes; defaults to
            ``bleach.ALLOWED_ATTRIBUTES``

        :arg styles: whitelist of allowed css; defaults to
            ``bleach.ALLOWED_STYLES``

        :arg protocols: whitelist of allowed protocols for links; defaults
            to ``bleach.ALLOWED_PROTOCOLS``

        :arg strip: whether or not to strip disallowed elements

        :arg strip_comments: whether or not to strip HTML comments

        :arg filters: list of html5lib Filter classes to pass streamed content through

            See http://html5lib.readthedocs.io/en/latest/movingparts.html#filters

            .. Warning::

               Using filters changes the output of ``bleach.Cleaner.clean``.
               Make sure the way the filters change the output are secure.

        """
        self.tags = tags
        self.attributes = attributes
        self.styles = styles
        self.protocols = protocols
        self.strip = strip
        self.strip_comments = strip_comments
        self.filters = filters or []

        self.parser = html5lib.HTMLParser(namespaceHTMLElements=False)
        self.walker = html5lib.getTreeWalker('etree')
        self.serializer = HTMLSerializer(
            quote_attr_values='always',
            omit_optional_tags=False,

            # Bleach has its own sanitizer, so don't use the html5lib one
            sanitize=False,

            # Bleach sanitizer alphabetizes already, so don't use the html5lib one
            alphabetical_attributes=False,
        )

    def clean(self, text):
        """Cleans text and returns sanitized result as unicode

        :arg str text: text to be cleaned

        :returns: sanitized text as unicode

        """
        if not text:
            return u''

        text = force_unicode(text)

        dom = self.parser.parseFragment(text)
        filtered = BleachSanitizerFilter(
            source=self.walker(dom),

            # Bleach-sanitizer-specific things
            allowed_attributes_map=self.attributes,
            strip_disallowed_elements=self.strip,
            strip_html_comments=self.strip_comments,

            # html5lib-sanitizer things
            allowed_elements=self.tags,
            allowed_css_properties=self.styles,
            allowed_protocols=self.protocols,
            allowed_svg_properties=[],
        )

        # Apply any filters after the BleachSanitizerFilter
        for filter_class in self.filters:
            filtered = filter_class(source=filtered)

        return self.serializer.render(filtered)


def clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES,
          styles=ALLOWED_STYLES, protocols=ALLOWED_PROTOCOLS, strip=False,
          strip_comments=True, filters=None):
    """Clean an HTML fragment of malicious content and return it

    This function is a security-focused function whose sole purpose is to
    remove malicious content from a string such that it can be displayed as
    content in a web page.

    This function is not designed to use to transform content to be used in
    non-web-page contexts.

    Example::

        import bleach

        better_text = bleach.clean(yucky_text)


    .. Note::

       If you're cleaning a lot of text and passing the same argument
       values, consider caching a ``Cleaner`` instance.

    :arg text: the text to clean

    :arg tags: whitelist of allowed tags; defaults to
        ``bleach.ALLOWED_TAGS``

    :arg attributes: whitelist of allowed attributes; defaults to
        ``bleach.ALLOWED_ATTRIBUTES``

    :arg styles: whitelist of allowed css; defaults to
        ``bleach.ALLOWED_STYLES``

    :arg protocols: whitelist of allowed protocols for links; defaults
        to ``bleach.ALLOWED_PROTOCOLS``

    :arg strip: whether or not to strip disallowed elements

    :arg strip_comments: whether or not to strip HTML comments

    :arg filters: list of html5lib Filter classes to pass streamed content through

        See http://html5lib.readthedocs.io/en/latest/movingparts.html#filters

        .. Warning::

           Using filters changes the output of
           ``bleach.Cleaner.clean``. Make sure the way the filters
           change the output are secure.

    :returns: cleaned text as unicode

    """
    cleaner = Cleaner(
        tags=tags,
        attributes=attributes,
        styles=styles,
        protocols=protocols,
        strip=strip,
        strip_comments=strip_comments,
        filters=filters,
    )
    return cleaner.clean(text)


def linkify(text, callbacks=DEFAULT_CALLBACKS, skip_pre=False,
            parse_email=False):
    """Convert URL-like strings in an HTML fragment to links

    ``linkify()`` converts strings that look like URLs, domain names and email
    addresses in text that may be an HTML fragment to links, while preserving:

    1. links already in the string
    2. urls found in attributes
    3. email addresses

    ``linkify()`` does a best-effort approach and tries to recover from bad
    situations due to crazy text.

    """
    text = force_unicode(text)

    if not text:
        return u''

    parser = html5lib.HTMLParser()

    forest = parser.parseFragment(text)
    _seen = set()

    def replace_nodes(tree, new_frag, node, index=0):
        """Doesn't really replace nodes, but inserts the nodes contained in
        ``new_frag`` into ``tree`` at position ``index`` and returns the number
        of nodes inserted.

        If ``node`` is passed in, it is removed from the resulting tree.

        :arg tree: tree
        :arg new_frag: fragment of html text to insert
        :arg node: the node to "replace"
        :arg index: the index position to focus on

        :returns: number of nodes inserted so that you can skip ahead

        """
        count = 0
        new_tree = parser.parseFragment(new_frag)
        # capture any non-tag text at the start of the fragment
        if new_tree.text:
            if index == 0:
                tree.text = (tree.text or '') + new_tree.text
            else:
                tree[index-1].tail = (tree[index-1].tail or '') + new_tree.text

        # then put in the tagged elements into the old tree
        for n in new_tree:
            if n.tag == ETREE_TAG('a'):
                _seen.add(n)
            tree.insert(index + count, n)
            count += 1

        # if we got a node to remove...
        if node is not None:
            # first, grab the node tail so we don't lose text
            if node.tail:
                if index + count == 0:
                    tree.text = (tree.text or '') + node.tail
                else:
                    tree[index+count-1].tail = (tree[index+count-1].tail or '') + node.tail
            tree.remove(node)
        return count

    def strip_wrapping_parentheses(fragment):
        """Strips wrapping parentheses.

        Returns a tuple of the following format::

            (string stripped from wrapping parentheses,
             count of stripped opening parentheses,
             count of stripped closing parentheses)
        """
        opening_parentheses = closing_parentheses = 0
        # Count consecutive opening parentheses
        # at the beginning of the fragment (string).
        for char in fragment:
            if char == '(':
                opening_parentheses += 1
            else:
                break

        if opening_parentheses:
            newer_frag = ''
            # Cut the consecutive opening brackets from the fragment.
            fragment = fragment[opening_parentheses:]
            # Reverse the fragment for easier detection of parentheses
            # inside the URL.
            reverse_fragment = fragment[::-1]
            skip = False
            for char in reverse_fragment:
                # Remove the closing parentheses if it has a matching
                # opening parentheses (they are balanced).
                if (char == ')' and
                        closing_parentheses < opening_parentheses and
                        not skip):
                    closing_parentheses += 1
                    continue
                # Do not remove ')' from the URL itself.
                elif char != ')':
                    skip = True
                newer_frag += char
            fragment = newer_frag[::-1]

        return fragment, opening_parentheses, closing_parentheses

    def apply_callbacks(attrs, new):
        for cb in callbacks:
            attrs = cb(attrs, new)
            if attrs is None:
                return None
        return attrs

    def _render_inner(node):
        out = ['' if node.text is None else node.text]
        for subnode in node:
            out.append(_render(subnode))
            if subnode.tail:
                out.append(subnode.tail)
        return ''.join(out)

    def linkify_nodes(tree, parse_text=True):
        children = len(tree)
        current_child = -1
        # start at -1 to process the parent first
        while current_child < len(tree):
            if not tree.text:
                return
            if current_child < 0:
                node = tree
                if parse_text and node.text:
                    new_txt = old_txt = node.text
                    if parse_email:
                        new_txt = re.sub(email_re, email_repl, node.text)
                        if new_txt and new_txt != node.text:
                            node.text = ''
                            adj = replace_nodes(tree, new_txt, None, 0)
                            children += adj
                            current_child += adj
                            linkify_nodes(tree, True)
                            continue

                    new_txt = re.sub(url_re, link_repl, new_txt)
                    if new_txt != old_txt:
                        node.text = ''
                        adj = replace_nodes(tree, new_txt, None, 0)
                        children += adj
                        current_child += adj
                        continue
            else:
                node = tree[current_child]

            if parse_text and node.tail:
                new_tail = old_tail = node.tail
                if parse_email:
                    new_tail = re.sub(email_re, email_repl, new_tail)
                    if new_tail != node.tail:
                        node.tail = ''
                        adj = replace_nodes(tree, new_tail, None,
                                            current_child + 1)
                        # Insert the new nodes made from my tail into
                        # the tree right after me. current_child+1
                        children += adj
                        continue

                new_tail = re.sub(url_re, link_repl, new_tail)
                if new_tail != old_tail:
                    node.tail = ''
                    adj = replace_nodes(tree, new_tail, None,
                                        current_child + 1)
                    children += adj

            if node.tag == ETREE_TAG('a') and not (node in _seen):
                if not node.get('href', None) is None:
                    attrs = dict(node.items())

                    _text = attrs['_text'] = _render_inner(node)

                    attrs = apply_callbacks(attrs, False)

                    if attrs is None:
                        # # <a> tag replaced by the text within it
                        adj = replace_nodes(tree, _text, node, current_child)
                        # pull back current_child by 1 to scan the new nodes
                        # again.
                        current_child -= 1
                    else:
                        text = force_unicode(attrs.pop('_text'))
                        for attr_key, attr_val in attrs.items():
                            node.set(attr_key, attr_val)

                        for n in reversed(list(node)):
                            node.remove(n)
                        text = parser.parseFragment(text)
                        node.text = text.text
                        for n in text:
                            node.append(n)
                        _seen.add(node)

            elif current_child >= 0:
                if node.tag == ETREE_TAG('pre') and skip_pre:
                    linkify_nodes(node, False)
                elif not (node in _seen):
                    linkify_nodes(node, parse_text)

            current_child += 1

    def email_repl(match):
        addr = match.group(0).replace('"', '&quot;')
        link = {
            '_text': addr,
            'href': 'mailto:{0!s}'.format(addr),
        }
        link = apply_callbacks(link, True)

        if link is None:
            return addr

        _href = link.pop('href')
        _text = link.pop('_text')

        repl = '<a href="{0!s}" {1!s}>{2!s}</a>'
        attr = '{0!s}="{1!s}"'
        attribs = ' '.join(attr.format(k, v) for k, v in link.items())
        return repl.format(_href, attribs, _text)

    def link_repl(match):
        url = match.group(0)
        open_brackets = close_brackets = 0
        if url.startswith('('):
            _wrapping = strip_wrapping_parentheses(url)
            url, open_brackets, close_brackets = _wrapping
        if url.endswith(')') and '(' not in url:
            # This is a clumsy handling for the case where we have something
            # like (foo http://example.com) and the ) gets picked up by the
            # url_re but we don't want it part of the link.
            new_url = url.rstrip(')')
            close_brackets += len(url) - len(new_url)
            url = new_url

        end = ''
        m = re.search(punct_re, url)
        if m:
            end = m.group(0)
            url = url[0:m.start()]
        if re.search(proto_re, url):
            href = url
        else:
            href = ''.join(['http://', url])

        link = {
            '_text': url,
            'href': href,
        }

        link = apply_callbacks(link, True)

        if link is None:
            return '(' * open_brackets + url + ')' * close_brackets

        _text = link.pop('_text')
        _href = link.pop('href')

        repl = '{0!s}<a href="{1!s}" {2!s}>{3!s}</a>{4!s}{5!s}'
        attr = '{0!s}="{1!s}"'
        attribs = ' '.join(attr.format(k, v) for k, v in link.items())

        return repl.format('(' * open_brackets,
                           _href, attribs, _text, end,
                           ')' * close_brackets)

    try:
        linkify_nodes(forest)
    except RuntimeError as e:
        # If we hit the max recursion depth, just return what we've got.
        log.exception('Probable recursion error: {0!r}'.format(e))

    return _render(forest)


def _render(tree):
    """Try rendering as HTML, then XML, then give up."""
    return force_unicode(_serialize(tree))


def _serialize(domtree):
    walker = html5lib.treewalkers.getTreeWalker('etree')
    stream = walker(domtree)
    serializer = HTMLSerializer(quote_attr_values='always',
                                alphabetical_attributes=True,
                                omit_optional_tags=False)
    return serializer.render(stream)
