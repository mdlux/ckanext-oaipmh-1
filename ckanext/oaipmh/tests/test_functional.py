# coding: utf-8
#
# pylint: disable=no-self-use, missing-docstring, too-many-public-methods, invalid-name
"""
Functional tests for OAI-PMH harvester.
"""

import datetime
from unittest import TestCase

import oaipmh.client
import ckan
import random

from ckan.model import Group
from ckanext.harvest import model as harvest_model
from ckanext.oaipmh import importformats
from ckanext.oaipmh.harvester import OAIPMHHarvester
import ckanext.kata.model as kata_model
import ckanext.kata.utils as utils

from ckan.tests import WsgiAppCase
from ckan.lib.helpers import url_for

import lxml.etree
from ckan.logic import get_action
from ckan import model
from ckanext.kata.tests.test_fixtures.unflattened import TEST_DATADICT

from copy import deepcopy
import os

from pylons.util import AttribSafeContextObj, PylonsContext, pylons


FIXTURE_LISTIDENTIFIERS = "listidentifiers.xml"
FIXTURE_DATASET = "oai-pmh.xml"


def _get_fixture(filename):
    return "file://%s" % os.path.join(os.path.dirname(__file__), "..", "test_fixtures", filename)


class TestReadingFixtures(TestCase):

    TEST_ID = "urn:nbn:fi:csc-ida2013032600070s"

    @classmethod
    def setup_class(cls):
        '''
        Setup database and variables
        '''
        model.repo.rebuild_db()
        harvest_model.setup()
        kata_model.setup()
        cls.harvester = OAIPMHHarvester()

        # The Pylons globals are not available outside a request. This is a hack to provide context object.
        c = AttribSafeContextObj()
        py_obj = PylonsContext()
        py_obj.tmpl_context = c
        pylons.tmpl_context._push_object(c)

    @classmethod
    def teardown_class(cls):
        ckan.model.repo.rebuild_db()

    def test_list(self):
        '''
        Parse ListIdentifiers result
        '''

        registry = importformats.create_metadata_registry()
        client = oaipmh.client.Client(_get_fixture(FIXTURE_LISTIDENTIFIERS), registry)
        identifiers = (header.identifier() for header in client.listIdentifiers(metadataPrefix='oai_dc'))

        assert 'oai:arXiv.org:hep-th/9801001' in identifiers
        assert 'oai:arXiv.org:hep-th/9801002' in identifiers
        assert 'oai:arXiv.org:hep-th/9801005' in identifiers
        assert 'oai:arXiv.org:hep-th/9801010' in identifiers

    def test_fetch(self):
        '''
        Parse example dataset
        '''
        registry = importformats.create_metadata_registry()
        client = oaipmh.client.Client(_get_fixture(FIXTURE_DATASET), registry)
        record = client.getRecord(identifier=self.TEST_ID, metadataPrefix='oai_dc')

        assert record

    def test_fetch_fail(self):
        '''
        Try to parse ListIdentifiers result as a dataset (basically testing PyOAI)
        '''
        def getrecord():
            client.getRecord(identifier=self.TEST_ID, metadataPrefix='oai_dc')

        registry = importformats.create_metadata_registry()
        client = oaipmh.client.Client(_get_fixture(FIXTURE_LISTIDENTIFIERS), registry)
        self.assertRaises(Exception, getrecord)


class TestOaipmhServer(WsgiAppCase, TestCase):
    """ Test OAI-PMH server """

    _namespaces = {'o': 'http://www.openarchives.org/OAI/2.0/',
                   'oai_dc': "http://www.openarchives.org/OAI/2.0/oai_dc/",
                   'dc': "http://purl.org/dc/elements/1.1/",
                   'dct': "http://purl.org/dc/terms/",
                   'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                   'rdfs': "http://www.w3.org/2000/01/rdf-schema#"}

    @classmethod
    def setup_class(cls):
        '''
        Setup database
        '''
        model.repo.rebuild_db()
        harvest_model.setup()
        kata_model.setup()

        # The Pylons globals are not available outside a request. This is a hack to provide context object.
        c = AttribSafeContextObj()
        py_obj = PylonsContext()
        py_obj.tmpl_context = c
        pylons.tmpl_context._push_object(c)

    @classmethod
    def teardown(cls):
        ckan.model.repo.rebuild_db()

    def _get_results(self, xml, xpath):
        return xml.xpath(xpath, namespaces=self._namespaces)

    def _get_single_result(self, xml, xpath):
        results = self._get_results(xml, xpath)
        self.assertEquals(len(results), 1)
        return results[0]

    def test_coverage(self):
        model.User(name="test_coverage", sysadmin=True).save()
        organization = get_action('organization_create')({'user': 'test_coverage'}, {'name': 'test-organization-coverage', 'title': "Test organization"})
        package_1_data = deepcopy(TEST_DATADICT)
        package_1_data['owner_org'] = organization['name']
        package_1_data['private'] = False
        for pid in package_1_data.get('pids', []):
            pid['id'] = utils.generate_pid()

        package = get_action('package_create')({'user': 'test_coverage'}, package_1_data)
        package_name = package['name']
        url = url_for('/oai')
        result = self.app.get(url, {'verb': 'GetRecord', 'identifier': package_name, 'metadataPrefix': 'oai_dc'})

        root = lxml.etree.fromstring(result.body)
        expected = ['Keilaniemi (populated place)', 'Espoo (city)', '2003-07-10T06:36:27-12:00/2010-04-15T03:24:47+12:45']

        found = 0
        for coverage in self._get_results(root, "//dc:coverage"):
            self.assertTrue(coverage.text in expected)
            found += 1
        self.assertEquals(3, found, "Unexpected coverage results")

        get_action('organization_delete')({'user': 'test_coverage'}, {'id': organization['id']})

    def test_coverage_spatial_rdf(self):
        organization = get_action('organization_create')({'user': 'test_coverage'}, {'name': 'test-organization-coverage-rdf', 'title': "Test organization rdf"})
        package_1_data = deepcopy(TEST_DATADICT)
        package_1_data['owner_org'] = organization['name']
        package_1_data['private'] = False
        for pid in package_1_data.get('pids', []):
            pid['id'] = utils.generate_pid()

        package = get_action('package_create')({'user': 'test_coverage'}, package_1_data)
        package_name = package['name']
        url = url_for('/oai')
        result = self.app.get(url, {'verb': 'GetRecord', 'identifier': package_name, 'metadataPrefix': 'rdf'})

        root = lxml.etree.fromstring(result.body)
        expected = ['Keilaniemi (populated place),Espoo (city)']

        found = 0
        for spatial in self._get_results(root, "//dct:spatial_ref/rdf:Description/dct:Location/rdf:Description/rdfs:label"):
            self.assertTrue(spatial.text in expected)
            found += 1
        self.assertEquals(1, found, "Unexpected coverage results")

        get_action('organization_delete')({'user': 'test_coverage'}, {'id': organization['id']})

    def test_coverage_temporal_rdf(self):
        """ For some reason _get_results(... "...*") finds temporal nodes four times.
        """
        organization = get_action('organization_create')({'user': 'test_coverage'}, {'name': 'test-organization-coverage-rdf2', 'title': "Test organization rdf 2"})
        package_1_data = deepcopy(TEST_DATADICT)
        package_1_data['owner_org'] = organization['name']
        package_1_data['private'] = False
        for pid in package_1_data.get('pids', []):
            pid['id'] = utils.generate_pid()

        package = get_action('package_create')({'user': 'test_coverage'}, package_1_data)
        package_name = package['name']
        url = url_for('/oai')
        result = self.app.get(url, {'verb': 'GetRecord', 'identifier': package_name, 'metadataPrefix': 'rdf'})

        root = lxml.etree.fromstring(result.body)
        expected = ['2003-07-10T06:36:27-12:00', '2010-04-15T03:24:47+12:45']

        found = 0
        for temporal in self._get_results(root, "//dct:temporal/dct:PeriodOfTime/*"):
            self.assertTrue(temporal.text in expected)
            found += 1
        self.assertEquals(4, found, "Unexpected coverage results: {f}".format(f=found))

        get_action('organization_delete')({'user': 'test_coverage'}, {'id': organization['id']})

    def test_records(self):
        """ Test record fetching via http-request to prevent accidental changes to interface """
        model.User(name="test", sysadmin=True).save()
        organization = get_action('organization_create')({'user': 'test'}, {'name': 'test-organization', 'title': "Test organization"})
        package_1_data = deepcopy(TEST_DATADICT)
        package_1_data['owner_org'] = organization['name']
        package_1_data['private'] = False
        package_2_data = deepcopy(package_1_data)

        for pid in package_1_data.get('pids', []):
            pid['id'] = utils.generate_pid()
        for pid in package_2_data.get('pids', []):
            pid['id'] = utils.generate_pid()

        packages = [get_action('package_create')({'user': 'test'}, package_1_data),
                    get_action('package_create')({'user': 'test'}, package_2_data)]

        url = url_for('/oai')
        result = self.app.get(url, {'verb': 'ListSets'})

        root = lxml.etree.fromstring(result.body)
        request_set = self._get_single_result(root, "//o:set")

        set_name = request_set.xpath("string(o:setName)", namespaces=self._namespaces)
        set_spec = request_set.xpath("string(o:setSpec)", namespaces=self._namespaces)
        self.assertEquals(organization['name'], set_spec)
        self.assertEquals(organization['title'], set_name)

        result = self.app.get(url, {'verb': 'ListIdentifiers', 'set': set_spec, 'metadataPrefix': 'oai_dc'})

        root = lxml.etree.fromstring(result.body)
        fail = True

        package_identifiers = [package['id'] for package in packages]
        package_org_names = [Group.get(package['owner_org']).name for package in packages]

        for header in root.xpath("//o:header", namespaces=self._namespaces):
            fail = False
            set_spec = header.xpath("string(o:setSpec)", namespaces=self._namespaces)
            identifier = header.xpath("string(o:identifier)", namespaces=self._namespaces)
            self.assertTrue(set_spec in package_org_names)
            self.assertTrue(identifier in package_identifiers)

            result = self.app.get(url, {'verb': 'GetRecord', 'identifier': identifier, 'metadataPrefix': 'oai_dc'})

            root = lxml.etree.fromstring(result.body)

            fail_record = True
            for record_result in root.xpath("//o:record", namespaces=self._namespaces):
                fail_record = False
                header = self._get_single_result(record_result, 'o:header')
                self._get_single_result(record_result, 'o:metadata')

                self.assertTrue(header.xpath("string(o:identifier)", namespaces=self._namespaces) in package_identifiers)
                self.assertTrue(header.xpath("string(o:setSpec)", namespaces=self._namespaces) in package_org_names)

            self.assertFalse(fail_record, "No records received")

        self.assertFalse(fail, "No headers (packages) received")

    def test_private_record(self):
        '''
        Test that private packages are not listed but public packages are

        '''
        package_1_data = deepcopy(TEST_DATADICT)
        model.User(name="privateuser", sysadmin=True).save()
        organization = get_action('organization_create')({'user': 'privateuser'}, {'name': 'private-organization', 'title': "Private organization"})
        package_1_data['private'] = True
        package_1_data['owner_org'] = organization['name']
        package_1_data['name'] = 'private-package'
        for pid in package_1_data.get('pids', []):
            pid['id'] = utils.generate_pid()
        package1 = get_action('package_create')({'user': 'privateuser'}, package_1_data)
        package_2_data = deepcopy(TEST_DATADICT)
        package_2_data['private'] = False
        package_2_data['owner_org'] = organization['name']
        package_2_data['name'] = 'public-package'
        for pid in package_2_data.get('pids', []):
            pid['id'] = utils.generate_pid()

        url = url_for('/oai')

        result = self.app.get(url, {'verb': 'ListIdentifiers', 'set': 'private-organization', 'metadataPrefix': 'oai_dc'})
        root = lxml.etree.fromstring(result.body)
        self.assertFalse(root.xpath("//o:header", namespaces=self._namespaces))

        now = datetime.datetime.isoformat(datetime.datetime.today())
        result = self.app.get(url, {'verb': 'ListRecords', 'set': 'private-organization', 'metadataPrefix': 'rdf', 'until': now})
        root = lxml.etree.fromstring(result.body)
        self.assertFalse(root.xpath("//o:header", namespaces=self._namespaces))

        package2 = get_action('package_create')({'user': 'privateuser'}, package_2_data)
        result = self.app.get(url, {'verb': 'ListIdentifiers', 'set': 'private-organization', 'metadataPrefix': 'oai_dc'})
        root = lxml.etree.fromstring(result.body)
        for header in root.xpath("//o:header", namespaces=self._namespaces):
            identifier = header.xpath("string(o:identifier)", namespaces=self._namespaces)
            print identifier
            self.assertTrue(identifier == package2['id'])

        result = self.app.get(url, {'verb': 'ListRecords', 'metadataPrefix': 'rdf'})
        root = lxml.etree.fromstring(result.body)
        for header in root.xpath("//o:header", namespaces=self._namespaces):
            identifier = header.xpath("string(o:identifier)", namespaces=self._namespaces)
            self.assertTrue(identifier == package2['id'])

        get_action('organization_delete')({'user': 'privateuser'}, {'id': organization['id']})
