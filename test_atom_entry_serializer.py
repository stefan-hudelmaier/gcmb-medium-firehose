"""Unit tests for atom_entry_serializer."""
import unittest
from datetime import datetime, timezone
from atoma import parse_atom_bytes
from atom_entry_serializer import serialize_atom_entry, AtomEntry, Author
import xml.etree.ElementTree as ET


class TestAtomEntrySerializer(unittest.TestCase):
    def setUp(self):
        # Sample Atom feed with one entry
        feed_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <status
            feed="https://medium.com/feed/tag/technology" xmlns="http://superfeedr.com/xmpp-pubsub-ext">
        <http
                code="200">Fetched (ping) 200 172800 and parsed 10/10 entries
        </http>
        <next_fetch>1970-01-21T05:06:27.691Z
        </next_fetch>
        <entries_count_since_last_maintenance>88</entries_count_since_last_maintenance>
        <velocity>476
        </velocity>
        <popularity>2.732975747430015</popularity>
        <generated_ids>true</generated_ids>
        <title>Technology on Medium
        </title>
        <period>172800</period>
        <last_fetch>1970-01-21T05:02:46.750Z</last_fetch>
        <last_parse>1970-01-21T05:02:46.750Z
        </last_parse>
        <last_maintenance_at>1970-01-21T05:02:34.655Z</last_maintenance_at>
    </status>
    <link
            rel="humans" href="https://medium.com/humans.txt"/>
    <link
            title="Technology on Medium" rel="alternate"
            href="https://medium.com/tag/technology/latest?source=rss------technology-5" type="text/html"/>
    <link
            title="Technology on Medium" rel="image"
            href="https://cdn-images-1.medium.com/proxy/1*TGH72Nnw24QL3iV9IOm4VA.png" type="image/png"/>
    <link
            title="Technology on Medium" rel="self" href="https://medium.com/feed/tag/technology"
            type="application/rss+xml"/>
    <link
            title="" rel="hub" href="http://medium.superfeedr.com" type="text/html"/>
    <title>Technology on Medium
    </title>
    <updated>2025-05-02T06:19:31.000Z</updated>
    <id>technology-on-medium-2025-5-2-6</id>

  <entry
            xmlns="http://www.w3.org/2005/Atom" xmlns:geo="http://www.georss.org/georss"
            xmlns:as="http://activitystrea.ms/spec/1.0/" xmlns:sf="http://superfeedr.com/xmpp-pubsub-ext">
        <id>
            https://medium.com/p/26bdcca8c014
        </id>
        <published>2025-05-02T05:53:16.000Z</published>
        <updated>2025-05-02T05:54:32.530Z</updated>
        <title>Why Developer Experience Portals Are the New Nerve Centers of the GenAI Age</title>
        <summary
                type="html">&lt;div class="medium-feed-item"&gt;&lt;p class="medium-feed-image"&gt;&lt;a
            href="https://medium.com/@OpenTurf/why-developer-experience-portals-are-the-new-nerve-centers-of-the-genai-age-26bdcca8c014?source=rss------technology-5"&gt;&lt;img
            src="https://cdn-images-1.medium.com/max/1400/0*n23wkzNjTpJxGqqO" width="1400"&gt;&lt;/a&gt;&lt;/p&gt;&lt;p
            class="medium-feed-snippet"&gt;In the current era of GenAI, software development has evolved beyond mere
            coding. It now encompasses integrating tools, knowledge, and the&amp;#x2026;&lt;/p&gt;&lt;p
            class="medium-feed-link"&gt;&lt;a
            href="https://medium.com/@OpenTurf/why-developer-experience-portals-are-the-new-nerve-centers-of-the-genai-age-26bdcca8c014?source=rss------technology-5"&gt;Continue
            reading on Medium \u00bb&lt;/a&gt;&lt;/p&gt;&lt;/div&gt;
        </summary>
        <link
                title="Why Developer Experience Portals Are the New Nerve Centers of the GenAI Age" rel="alternate"
                href="https://medium.com/@OpenTurf/why-developer-experience-portals-are-the-new-nerve-centers-of-the-genai-age-26bdcca8c014?source=rss------technology-5"
                type="text/html"/>
        <author>
            <name>OpenTurf Technologies</name>
            <uri></uri>
            <email></email>
            <id>OpenTurf Technologies</id>
        </author>
        <category term="coding"/>
        <category term="gen-ai-services"/>
        <category term="technology"/>
        <category
                term="developer-portal"/>
        <category term="ai-tools-for-business"/>
    </entry>
</feed>'''
        # Parse the feed using atoma
        feed = parse_atom_bytes(feed_xml.encode('utf-8'))
        self.sample_entry = feed.entries[0]

    def test_serialize_atom_entry(self):
        """Test that an Atom entry is correctly serialized."""
        result = serialize_atom_entry(self.sample_entry)

        self.assertIsInstance(result, AtomEntry)
        
        # Test basic fields
        self.assertEqual(result.id, "https://medium.com/p/26bdcca8c014")
        self.assertEqual(result.title, "Why Developer Experience Portals Are the New Nerve Centers of the GenAI Age")
        self.assertEqual(result.published, datetime(2025, 5, 2, 5, 53, 16, tzinfo=timezone.utc))
        self.assertEqual(result.updated, datetime(2025, 5, 2, 5, 54, 32, 530000, tzinfo=timezone.utc))
        
        # Test author
        self.assertIsInstance(result.author, Author)
        self.assertEqual(result.author.name, "OpenTurf Technologies")
        self.assertIsNone(result.author.uri)
        self.assertIsNone(result.author.email)
        
        # Test categories
        expected_categories = [
            "coding",
            "gen-ai-services",
            "technology",
            "developer-portal",
            "ai-tools-for-business"
        ]
        self.assertEqual(result.categories, expected_categories)
        
        # Test link
        expected_link = "https://medium.com/@OpenTurf/why-developer-experience-portals-are-the-new-nerve-centers-of-the-genai-age-26bdcca8c014?source=rss------technology-5"
        self.assertEqual(result.link, expected_link)
        self.assertEqual(result.link_type, "text/html")
        
        # Test summary
        self.assertTrue(result.summary.startswith('<div class="medium-feed-item">'))
        self.assertTrue(result.summary.endswith('</div>'))

    def test_atom_entry_to_xml(self):
        """Test that an AtomEntry can be converted to XML."""
        atom_entry = serialize_atom_entry(self.sample_entry)
        xml_elem = atom_entry.to_xml()
        
        # Test XML structure
        self.assertEqual(xml_elem.tag, 'entry')
        self.assertEqual(xml_elem.attrib['xmlns'], 'http://www.w3.org/2005/Atom')
        
        # Test basic fields
        self.assertEqual(xml_elem.find('id').text, "https://medium.com/p/26bdcca8c014")
        self.assertEqual(xml_elem.find('title').text, "Why Developer Experience Portals Are the New Nerve Centers of the GenAI Age")
        self.assertEqual(xml_elem.find('published').text, "2025-05-02T05:53:16.000Z")
        self.assertEqual(xml_elem.find('updated').text, "2025-05-02T05:54:32.530Z")
        
        # Test author
        author_elem = xml_elem.find('author')
        self.assertEqual(author_elem.find('name').text, "OpenTurf Technologies")
        self.assertIsNone(author_elem.find('uri'))  # Empty URI should not be included
        self.assertIsNone(author_elem.find('email'))  # Empty email should not be included
        
        # Test categories
        categories = [elem.attrib['term'] for elem in xml_elem.findall('category')]
        expected_categories = [
            "coding",
            "gen-ai-services",
            "technology",
            "developer-portal",
            "ai-tools-for-business"
        ]
        self.assertEqual(categories, expected_categories)
        
        # Test link
        link_elem = xml_elem.find('link')
        self.assertEqual(link_elem.attrib['href'], "https://medium.com/@OpenTurf/why-developer-experience-portals-are-the-new-nerve-centers-of-the-genai-age-26bdcca8c014?source=rss------technology-5")
        self.assertEqual(link_elem.attrib['type'], "text/html")
        self.assertEqual(link_elem.attrib['rel'], "alternate")
        
        # Test summary
        summary_elem = xml_elem.find('summary')
        self.assertEqual(summary_elem.attrib['type'], "html")
        self.assertTrue(summary_elem.text.startswith('<div class="medium-feed-item">'))
        self.assertTrue(summary_elem.text.endswith('</div>'))

    def test_atom_entry_to_xml_string(self):
        """Test that an AtomEntry can be converted to an XML string."""
        atom_entry = serialize_atom_entry(self.sample_entry)
        xml_str = atom_entry.to_xml_string()
        
        # Basic validation that it's a well-formed XML string
        try:
            ET.fromstring(xml_str)
        except ET.ParseError:
            self.fail("Generated XML string is not well-formed")
        
        # Check for key elements in the string (ignoring whitespace and self-closing tags)
        self.assertIn('<entry xmlns="http://www.w3.org/2005/Atom">', xml_str)
        self.assertIn('<id>https://medium.com/p/26bdcca8c014</id>', xml_str)
        self.assertIn('<title>Why Developer Experience Portals Are the New Nerve Centers of the GenAI Age</title>', xml_str)
        self.assertIn('<name>OpenTurf Technologies</name>', xml_str)
        self.assertIn('term="coding"', xml_str)
        self.assertIn('<summary type="html">', xml_str)
        self.assertNotIn('<uri>', xml_str)  # Empty URI should not be included
        self.assertNotIn('<email>', xml_str)  # Empty email should not be included


if __name__ == '__main__':
    unittest.main()
