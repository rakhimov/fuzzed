'''
    This is the test suite.

    The typical workflow to add new tests is the following:
    - Get yourself an empty local database with './manage.py flush'.
    - Draw one or more test graphs. 
    - Create a fixture file from it with 'fab fixture_save:<filename.json>'. 
    - Create a class such as 'SimpleFixtureTestCase' to wrap all ID's for your fixture file.
    - Derive your test case class from it. Check the helper functions in 'FuzzEdTestCase'.
    - Run the tests with 'fab run_tests'.
    - Edit your fixture file by loading it into the local database with 'fab fixture_load:<filename.json>'

    TODO: Several test would look better if the model is checked afterwards for the changes being applied
        (e.g. node relocation). Since we use the LiveServerTestCase base, this is not possible, since
        database modifications are not commited at all. Explicit comitting did not help ...
'''

import json, logging, time, os, tempfile, subprocess, unittest
from xml.dom import minidom
from subprocess import Popen
from django.db import transaction
from django.test import LiveServerTestCase
from django.test.utils import override_settings
from django.test.client import Client
from FuzzEd.models.graph import Graph
from FuzzEd.models.node import Node
from tastypie.exceptions import Unauthorized, UnsupportedFormat

# This disables all the debug output from the FuzzEd server, e.g. Latex rendering nodes etc.
#logging.disable(logging.CRITICAL)

class FuzzEdTestCase(LiveServerTestCase):
    '''
        The base class for all test cases. Mainly provides helper functions for deal with auth stuff.
    '''
    def setUpAnonymous(self):
        ''' If the test case wants to have a anonymous login session, it should call this function in setUp().'''
        self.c=Client()

    def setUpLogin(self):
        ''' If the test case wants to have a functional login session, it should call this function in setUp().'''
        self.c=Client()
        self.c.login(username='testadmin', password='testadmin') 

    def get(self, url):
        return self.c.get(url)

    def post(self, url, data):
        return self.c.post(url, data)

    def getWithAPIKey(self, url):
        return self.c.get(url, **{'HTTP_AUTHORIZATION':'ApiKey testadmin:f1cc367bc09fc95720e6c8a4225ae2b912fff91b'})

    def postWithAPIKey(self, url, data, content_type):
        return self.c.post(url, data, content_type, **{'HTTP_AUTHORIZATION':'ApiKey testadmin:f1cc367bc09fc95720e6c8a4225ae2b912fff91b'})

    def ajaxGet(self, url):
        return self.c.get( url, HTTP_X_REQUESTED_WITH = 'XMLHttpRequest' )

    def ajaxPost(self, url, data):
        return self.c.post( url, data, HTTP_X_REQUESTED_WITH = 'XMLHttpRequest' )

    def ajaxDelete(self, url):
        return self.c.delete( url, HTTP_X_REQUESTED_WITH = 'XMLHttpRequest' )

    def requestJob(self, url):
        """ Helper function for requesting a job. """ 
        response=self.ajaxGet(url)
        self.assertNotEqual(response.status_code, 500) # the backend daemon is not started
        self.assertEqual(response.status_code, 201)    # test if we got a created job
        assert('Location' in response)
        jobUrl = response['Location']
        code = 202
        print "Waiting for result from "+jobUrl,
        while (code == 202):
            response=self.ajaxGet(jobUrl)
            code = response.status_code 
            print ".",
        self.assertEqual(response.status_code, 200)
        return response.content

    def requestAnalysis(self, graph_id):
        """ Helper function for requesting an analysis run. 
            Returns the analysis result as dictionary as received by the frontend.
        """
        url=self.ajaxGet('/api/graphs/%u/analysis/topEventProbability'%graph_id)
        data = self.requestJob(url)
        return json.loads(data)

class SimpleFixtureTestCase(FuzzEdTestCase):
    ''' 
        This is a base class that wraps all information about the 'simple' fixture. 
    '''
    fixtures = ['simple.json', 'initial_data.json']
    graphs = {1: 'faulttree', 2: 'fuzztree', 3: 'rbd'}
    # A couple of specific PK's from the model
    pkProject = 1
    pkFaultTree = 1
    clientIdEdge = 4
    clientIdAndGate = 1
    clientIdBasicEvent = 2

class ViewsTestCase(SimpleFixtureTestCase):
    ''' 
        Tests for different Django views and their form submissions. 
    '''
    def setUp(self):
        self.setUpLogin()        
    def testRootView(self):
        ''' Root view shall redirect to projects overview. '''
        response=self.get('/')
        self.assertEqual(response.status_code, 302)
    def testProjectsView(self):
        response=self.get('/projects/')
        self.assertEqual(response.status_code, 200)
    def testEditorView(self):
        for id, kind in self.graphs.iteritems():
            response=self.get('/editor/%u'%id)
            self.assertEqual(response.status_code, 200)
    def testInvalidEditorView(self):
        response=self.get('/editor/999')
        self.assertEqual(response.status_code, 404)
    def testGraphCopy(self):
        for graphid, kind in self.graphs.iteritems():
            response = self.post('/graphs/%u/'%graphid, {'copy': 'copy'})
            self.assertEqual(response.status_code, 302)
            # The view code has no reason to return the new graph ID, so the redirect is to the dashboard
            # We therefore determine the new graph by the creation time
            copy = Graph.objects.all().order_by('-created')[0]
            original = Graph.objects.get(pk=graphid)
            self.assertTrue(original.same_as(copy))


class ExternalAPITestCase(SimpleFixtureTestCase):
    ''' 
        Tests for the Tastypie API. 
    '''
    def setUp(self):
        self.setUpAnonymous()        

    def testMissingAPIKey(self):
        response=self.get('/api/v1/project/?format=json')
        self.assertEqual(response.status_code, 401)

    def testRootResource(self):
        ''' Root view of external API should provide graph and project resource base URLs, even without API key.'''
        response=self.get('/api/v1/?format=json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        assert('graph' in data)
        assert('project' in data)

    def testProjectListResource(self):
        response=self.getWithAPIKey('/api/v1/project/?format=json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        assert('objects' in data)
        assert('graphs' in data['objects'][0])

    def testGraphListResource(self):
        response=self.getWithAPIKey('/api/v1/graph/?format=json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

    def testSingleProjectResource(self):
        response=self.getWithAPIKey('/api/v1/project/%u/?format=json'%self.pkProject)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

    def testJsonExport(self):
        for id, kind in self.graphs.iteritems():
            response=self.get('/api/v1/graph/%u/?format=json'%id)
            self.assertEqual(response.status_code, 401)
            response=self.getWithAPIKey('/api/v1/graph/%u/?format=json'%id)
            data = json.loads(response.content)
            self.assertEqual(response.status_code, 200)

    def testLatexExport(self):
        for id, kind in self.graphs.iteritems():
            if kind in ['faulttree','fuzztree']:
                response=self.get('/api/v1/graph/%u/?format=tex'%id)
                self.assertEqual(response.status_code, 401)
                response=self.getWithAPIKey('/api/v1/graph/%u/?format=tex'%id)
                self.assertEqual(response.status_code, 200)
                assert("tikz" in response.content)

    def testGraphmlExport(self):
        for id, kind in self.graphs.iteritems():
            if kind in ['faulttree','fuzztree']:
                # Should only be possible with API key authentication
                response=self.get('/api/v1/graph/%u/?format=graphml'%id)
                self.assertEqual(response.status_code, 401)
                response=self.getWithAPIKey('/api/v1/graph/%u/?format=graphml'%id)
                self.assertEqual(response.status_code, 200)
                assert("<graphml" in response.content)

    def testGraphmlImport(self):
        for id, kind in self.graphs.iteritems():
                # First export GraphML
                response=self.getWithAPIKey('/api/v1/graph/%u/?format=graphml'%id)
                self.assertEqual(response.status_code, 200)
                graphml = response.content
                # Now import the same GraphML
                response=self.postWithAPIKey('/api/v1/graph/?format=graphml&project=%u'%self.pkProject, graphml, 'application/xml')
                self.assertEqual(response.status_code, 201)
                # Check if the claimed graph really was created
                newid = int(response['Location'][-2])
                original = Graph.objects.get(pk=id)
                copy = Graph.objects.get(pk=newid)
                self.assertTrue(original.same_as(copy))

    def testInvalidGraphImportProject(self):
        # First export valid GraphML
        response=self.getWithAPIKey('/api/v1/graph/%u/?format=graphml'%self.pkFaultTree)
        self.assertEqual(response.status_code, 200)
        graphml = response.content
        with self.assertRaises(Unauthorized):
            self.postWithAPIKey('/api/v1/graph/?format=graphml&project=99', graphml, 'application/xml')

    def testInvalidGraphImportFormat(self):
        for wrong_format in ['json','tex','xml']:
            with self.assertRaises(UnsupportedFormat):
                self.postWithAPIKey('/api/v1/graph/?format=%s&project=%u'%(wrong_format,self.pkProject), "<graphml></graphml>", 'application/text')

    def testFoo(self):
        ''' Leave this out, and the last test will fail. Dont ask me why.'''
        assert(True)

class FrontendApiTestCase(SimpleFixtureTestCase):
    ''' 
        Tests for the Frontend API called from JavaScript. 
    '''
    def setUp(self):
        self.setUpLogin()        

    def testGetGraph(self):
        for id, kind in self.graphs.iteritems():
            response=self.ajaxGet('/api/graphs/%u'%self.pkFaultTree)
            self.assertEqual(response.status_code, 200)
        response=self.ajaxGet('/api/graphs/9999')
        self.assertEqual(response.status_code, 404)

    def testCreateNode(self):
        newnode = {'y'         : '3', 
                   'x'         : '7', 
                   'kind'      : 'basicEvent', 
                   'id'        : '1383517229910', 
                   'properties': '{}'}

        response=self.ajaxPost('/api/graphs/%u/nodes'%self.pkFaultTree, newnode)
        self.assertEqual(response.status_code, 201)
        newid = int(response['Location'][-2])
        newnode = Node.objects.get(pk=newid)

    def testDeleteNode(self):
        response=self.ajaxDelete('/api/graphs/%u/nodes/%u'%(self.pkFaultTree, self.clientIdBasicEvent))
        self.assertEqual(response.status_code, 204)

    def testRelocateNode(self):
        newpos = {'properties': '{"y":"3","x":"7"}'}
        response = self.ajaxPost('/api/graphs/%u/nodes/%u'%(self.pkFaultTree, self.clientIdBasicEvent), newpos)
        self.assertEqual(response.status_code, 204)

    def testPropertyChange(self):
        newprop = {'properties': '{"key": "foo", "value":"bar"}'}
        response = self.ajaxPost('/api/graphs/%u/nodes/%u'%(self.pkFaultTree, self.clientIdBasicEvent), newprop)
        self.assertEqual(response.status_code, 204)

    def testDeleteEdge(self):
        response=self.ajaxDelete('/api/graphs/%u/edges/%u'%(self.pkFaultTree, self.clientIdEdge))
        self.assertEqual(response.status_code, 204)

    def testCreateEdge(self):
        response=self.ajaxPost('/api/graphs/%u/edges'%self.pkFaultTree, {'id': 4714, 'source':self.clientIdAndGate, 'target':self.clientIdBasicEvent} )
        self.assertEqual(response.status_code, 201)

class BackendTestCase(SimpleFixtureTestCase):
    ''' 
        Tests for backend functionality. 
    '''

    def setUp(self):
        # Start up backend daemon in testing mode so that it uses port 8081 of the live test server
        print "Starting backend daemon"
        os.chdir("backends")
        self.backend = Popen(["python","daemon.py","--testing"])
        time.sleep(2)
        os.chdir("..")
        self.setUpLogin()        

    def tearDown(self):
        print "\nShutting down backend daemon"
        self.backend.terminate()

    @unittest.skip("")
    def testStandardFixtureAnalysis(self):
        result=self.requestAnalysis(4)
        self.assertEqual(bool(result['validResult']),True)
        self.assertEqual(result['errors'],{})
        self.assertEqual(result['warnings'],{})
        self.assertEqual(result['configurations'][0]['alphaCuts']['1.0'],[0.5, 0.5])
        self.assertEqual(result['configurations'][1]['alphaCuts']['1.0'],[0.4, 0.4])

    @unittest.skip("")
    def testIssue150(self):
        result=self.requestAnalysis(4)
        # This tree can lead to a k=0 redundancy configuration, which is not allowed
        self.assertEqual(result['validResult'],False)

    def testFrontendAPIPdfExport(self):
        pdfLink = self.requestJob('/api/graphs/%u/exports/pdf'%self.pkFaultTree)
        # The result of a PDF rendering job is the download link
        pdfResponse = self.get(pdfLink)
        self.assertEqual('application/pdf', pdfResponse['CONTENT-TYPE'])

    def testFrontendAPIEpsExport(self):
        epsLink = self.requestJob('/api/graphs/%u/exports/eps'%self.pkFaultTree)
        # The result of a EPS rendering job is the download link
        epsResponse = self.get(epsLink)
        self.assertEqual('application/postscript', epsResponse['CONTENT-TYPE'])
