# coding: utf-8

from oaipmh.common import Metadata
from importcore import generic_xml_metadata_reader, generic_rdf_metadata_reader
from lxml import etree

def copy_element(source, dest, md, callback = None):
	if source in md:
		md[dest] = md[dest + '.0'] = md[source]
		md[dest + '.count'] = 1
		if callback: callback(source, dest)
		return
	count = md.get(source + '.count', 0)
	md[dest + '.count'] = count
	for i in range(count):
		source_n = '%s.%d' % (source, i)
		dest_n = '%s.%d' % (dest, i)
		md[dest_n] = md[dest] = md[source_n]
		src_lang = source_n + '/language'
		dst_n_lang = dest_n + '/language'
		dst_lang = dest + '/language'
		if src_lang in md: md[dst_n_lang] = md[dst_lang] = md[src_lang]
		src_lang = source_n + '/@lang'
		if src_lang in md: md[dst_n_lang] = md[dst_lang] = md[src_lang]
		if callback: callback(source_n, dest_n)

def nrd_metadata_reader(xml):
	result = generic_rdf_metadata_reader(xml).getMap()

	def person_attrs(source, dest):
		# TODO: here we could also fetch from ISNI/ORCID
		copy_element(source + '/foaf:name', dest + '/name', result)
		copy_element(source + '/foaf:mbox', dest + '/email', result)
		copy_element(source + '/foaf:phone', dest + '/phone', result)

	def document_attrs(source, dest):
		copy_element(source + '/dct:title', dest + '/title', result)
		copy_element(source + '/dct:identifier', dest, result)
		copy_element(source + '/dct:creator',
				dest + '/creator/name', result)
		copy_element(source + '/nrd:creator', dest + '/creator',
				result, person_attrs)
		copy_element(source + '/dct:description',
				dest + '/description', result)

	def funding_attrs(source, dest):
		copy_element(source + '/rev:arpfo:funds.0/arpfo:grantNumber.0',
				dest + '/fundingNumber', result)
		copy_element(source + '/rev:arpfo:funds.0/rev:arpfo:provides.0',
				dest + '/funder', result,
				person_attrs)

	def file_attrs(source, dest):
		copy_element(source + '/dcat:mediaType',
				dest + '/mimetype', result)
		copy_element(source + '/fp:checksum.0/fp:checksumValue.0',
				dest + '/checksum.0', result)
		copy_element(source + '/fp:checksum.0/fp:generator.0',
				dest + '/checksum.0/algorithm', result)
		copy_element(source + '/dcat:byteSize', dest + '/size', result)

	mapping = [(u'dataset', u'versionidentifier', None),
		(u'dataset/nrd:continuityIdentifier', u'continuityidentifier',
			None),
		(u'dataset/rev:foaf:primaryTopic.0/nrd:metadataIdentifier',
			u'metadata/identifier', None),
		(u'dataset/rev:foaf:primaryTopic.0/nrd:metadataModified',
			u'metadata/modified', None),
		(u'dataset/dct:title', u'title', None),
		(u'dataset/nrd:modified', u'modified', None),
		(u'dataset/nrd:rights', u'rights', None),
		(u'dataset/nrd:language', u'language', None),
		(u'dataset/nrd:owner', u'owner', person_attrs),
		(u'dataset/nrd:creator', u'creator', person_attrs),
		(u'dataset/nrd:distributor', u'distributor', person_attrs),
		(u'dataset/nrd:contributor', u'contributor', person_attrs),
		(u'dataset/nrd:subject', u'subject', None), # fetch tags?
		(u'dataset/nrd:producerProject', u'project', funding_attrs),
		(u'dataset/dct:isPartOf', u'collection', document_attrs),
		(u'dataset/dct:requires', u'requires', None),
		(u'dataset/nrd:discipline', u'discipline', None),
		(u'dataset/nrd:temporal', u'temporalCoverage', None),
		(u'dataset/nrd:spatial', u'spatialCoverage', None), # names?
		(u'dataset/nrd:manifestation', u'resource', file_attrs),
		(u'dataset/nrd:observationMatrix', u'structure', None), # TODO
		(u'dataset/nrd:usedByPublication', u'publication',
			document_attrs),
		(u'dataset/dct:description', u'description', None),
	]
	for source, dest, callback in mapping:
		copy_element(source, dest, result, callback)
	try:
		rights = etree.XML(result[u'rights'])
		rightsclass = rights.attrib['RIGHTSCATEGORY'].lower()
		result[u'rightsclass'] = rightsclass
		if rightsclass == 'licensed':
			result[u'license'] = rights[0].text
		if rightsclass == 'contractual':
			result[u'accessURL'] = rights[0].text
	except: pass
	return Metadata(result)

def dc_metadata_reader(xml):
	result = generic_xml_metadata_reader(xml)
	return result
