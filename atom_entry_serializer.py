"""
Serializer for Atom feed entries parsed by atoma library.
"""
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass
class Author:
    """Represents an author in an Atom entry."""
    name: str
    uri: Optional[str] = None
    email: Optional[str] = None


@dataclass
class AtomEntry:
    """Represents a serialized Atom entry."""
    id: str
    published: datetime
    updated: datetime
    title: str
    summary: str
    link: str
    link_type: str
    author: Author
    categories: List[str]

    def to_xml(self) -> ET.Element:
        """Convert the AtomEntry to an XML Element."""
        # Create the entry element with Atom namespace
        entry = ET.Element('entry', {'xmlns': 'http://www.w3.org/2005/Atom'})

        # Add basic fields
        ET.SubElement(entry, 'id').text = self.id
        ET.SubElement(entry, 'published').text = self.published.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        ET.SubElement(entry, 'updated').text = self.updated.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        ET.SubElement(entry, 'title').text = self.title

        # Add author
        author_elem = ET.SubElement(entry, 'author')
        ET.SubElement(author_elem, 'name').text = self.author.name
        if self.author.uri:
            ET.SubElement(author_elem, 'uri').text = self.author.uri
        if self.author.email:
            ET.SubElement(author_elem, 'email').text = self.author.email

        # Add categories
        for category in self.categories:
            ET.SubElement(entry, 'category', {'term': category})

        # Add link
        ET.SubElement(entry, 'link', {
            'title': self.title,
            'rel': 'alternate',
            'href': self.link,
            'type': self.link_type
        })

        # Add summary
        ET.SubElement(entry, 'summary', {'type': 'html'}).text = self.summary

        return entry

    def to_xml_string(self, pretty_print: bool = True) -> str:
        """Convert the AtomEntry to an XML string.
        
        Args:
            pretty_print: If True, format the XML with indentation
            
        Returns:
            str: The XML representation of the entry
        """
        elem = self.to_xml()
        
        # Convert to string
        xml_str = ET.tostring(elem, encoding='unicode')
        
        if pretty_print:
            import xml.dom.minidom
            xml_str = xml.dom.minidom.parseString(xml_str).toprettyxml(indent='  ')
        
        return xml_str


def _to_atom_entry(entry) -> AtomEntry:
    """
    Serializes an Atom entry parsed by atoma into our internal representation.
    
    Args:
        entry: An Atom entry object parsed by atoma
        
    Returns:
        AtomEntry: Our internal representation of the Atom entry
    """
    # Extract author information from the first author
    first_author = entry.authors[0] if entry.authors else None
    author = Author(
        name=first_author.name if first_author else "",
        uri=first_author.uri if first_author and first_author.uri else None,
        email=first_author.email if first_author and first_author.email else None
    )
    
    # Extract link information
    link = ""
    link_type = ""
    if entry.links:
        for link_entry in entry.links:
            if link_entry.rel == "alternate":
                link = link_entry.href
                link_type = link_entry.type_
                break
    
    # Extract categories
    categories = [category.term for category in entry.categories] if entry.categories else []
    
    return AtomEntry(
        id=entry.id_.strip(),
        published=entry.published,
        updated=entry.updated,
        title=entry.title.value.strip(),
        summary=entry.summary.value if hasattr(entry.summary, 'value') else entry.summary,
        link=link,
        link_type=link_type,
        author=author,
        categories=categories
    )

def serialize_atom_entry(atoma_entry) -> str:
    atom_entry = _to_atom_entry(atoma_entry)
    return atom_entry.to_xml_string()