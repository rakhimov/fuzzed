from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from FuzzEd.decorators import require_ajax
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.core.urlresolvers import reverse
from FuzzEd.middleware import HttpResponse, HttpResponseAccepted, HttpResponseRedirect
from django.views.decorators.cache import never_cache

# We expect these imports to go away main the main logic finally lives in common.py
from django.shortcuts import get_object_or_404
from FuzzEd.models import Graph, notations, commands, Node, Job, Notification, NodeGroup, Graph, Project, Edge
from FuzzEd.middleware import *
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.mail import mail_managers

import logging
logger = logging.getLogger('FuzzEd')

import json, common
from tastypie.authentication import SessionAuthentication   

class EdgeResource(common.EdgeResource):
    class Meta:
        queryset = Edge.objects.filter(deleted=False)
        authentication = SessionAuthentication()
        serializer = common.EdgeSerializer()
        authorization = common.GraphOwnerAuthorization()
        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get', 'post']
        excludes = ['deleted', 'id']

class GraphSerializer(common.GraphSerializer):
    '''
        The frontend gets its own JSON format for the graph information,
        not the default HATEOAS format generated by Tastypie-
    '''
    def to_json(self, data, options=None):
        return data.obj.to_json()

class GraphResource(common.GraphResource):
    class Meta:
        queryset = Graph.objects.filter(deleted=False)
        authentication = SessionAuthentication()
        authorization = common.GraphAuthorization()
        allowed_methods = ['get', 'post']
        serializer = GraphSerializer()
        excludes = ['deleted', 'owner', 'read_only']

    def prepend_urls(self):
        return [
            url(r'^graphs/(?P<pk>\d+)/graph_download/$', 
                self.wrap_view('dispatch_detail'), 
                name = 'frontend_graph_download'),
            url(r'^graphs/(?P<pk>\d+)$', 
                self.wrap_view('dispatch_detail'), 
                name = 'graph'),
            url(r'^graphs/(?P<pk>\d+)/analysis/cutsets$', 
                self.wrap_view('dispatch_detail'), 
                name = 'analyze_cutsets'),
            url(r'^graphs/(?P<pk>\d+)/analysis/topEventProbability$', 
                self.wrap_view('dispatch_detail'), 
                name = 'analyze_top_event_probability'),
            url(r'^graphs/(?P<pk>\d+)/simulation/topEventProbability$', 
                self.wrap_view('dispatch_detail'), 
                name = 'simulation_top_event_probability'),
            url(r'^graphs/(?P<pk>\d+)/edges/$',
                self.wrap_view('dispatch_edges'),
                name="edges"),
            url(r'^graphs/(?P<pk>\d+)/nodes/$',
                self.wrap_view('dispatch_nodes'),
                name="edges"),
        ]

    def dispatch_edges(self, request, **kwargs):
        #TODO: Add some error handling if the provided graph pk is invalid
        bundle = self.build_bundle(data={'pk': kwargs['pk']}, request=request)
        obj = self.cached_obj_get(bundle=bundle, **self.remove_api_resource_names(kwargs))
        edge_resource = EdgeResource()
        return edge_resource.dispatch_list(request, graph=obj)

    def dispatch_nodes(self, request, **kwargs):
        #TODO: Add some error handling if the provided graph pk is invalid
        bundle = self.build_bundle(data={'pk': kwargs['pk']}, request=request)
        obj = self.cached_obj_get(bundle=bundle, **self.remove_api_resource_names(kwargs))
        node_resource = NodeResource()
        return node_resource.dispatch_list(request, graph=obj)


class ProjectResource(common.ProjectResource):
    class Meta:
        queryset = Project.objects.filter(deleted=False)
        authentication = SessionAuthentication()
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        excludes = ['deleted', 'owner']
        nested = 'graph'

class NodeResource(common.NodeResource):
    class Meta:
        queryset = Node.objects.filter(deleted=False)
        authentication = SessionAuthentication()
        authorization = common.GraphOwnerAuthorization()
        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get', 'post']
        excludes = ['deleted', 'id']        

    def prepend_urls(self):
        return [
            url(r'^graphs/(?P<graph_id>\d+)/nodes/(?P<pk>\d+)$', 
                self.wrap_view('dispatch_detail'), 
                name = 'node'),
            url(r'^graphs/(?P<graph_id>\d+)/nodes$', 
                self.wrap_view('dispatch_detail'), 
                name = 'nodes'),
        ]

class NodeGroupResource(common.NodeGroupResource):
    class Meta:
        queryset = NodeGroup.objects.filter(deleted=False)
        authentication = SessionAuthentication()
        authorization = common.GraphOwnerAuthorization()
        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get', 'post']

    def prepend_urls(self):
        return [
            url(r'^graphs/(?P<graph_id>\d+)/nodegroups/(?P<pk>\d+)$', 
                self.wrap_view('dispatch_detail'), 
                name = 'nodegroup'),
            url(r'^graphs/(?P<graph_id>\d+)/nodegroups$', 
                self.wrap_view('dispatch_detail'), 
                name = 'nodegroups'),
        ]


class JobResource(common.JobResource):
    class Meta:
        queryset = Job.objects
        authentication = SessionAuthentication()
        authorization = common.GraphOwnerAuthorization()
        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get', 'post']

    def prepend_urls(self):
        return [
            url(r'^jobs/(?P<pk>\d+)$', 
                self.wrap_view('dispatch_detail'), 
                name = 'frontend_job_status'),
        ]

@login_required
@csrf_exempt
@require_GET
def job_status(request, job_id):
    ''' Returns the status information for the given job.
        202 is delivered if the job is pending, otherwise the result is immediately returned.
        The result may be the actual text data, or a download link to a binary file.
    '''
    status, job = common.job_status(request.user, job_id)

    if status == 0:     # done, valid result
        if job.requires_download():
            # Return the URL to the file created by the job
            return HttpResponse(job.get_absolute_url())
        else:
            # Serve directly
            return HttpResponse(job.result_rendering())
    elif status == 1:   # done and error
        raise HttpResponseServerErrorAnswer("We have an internal problem analyzing this graph. Sorry! The developers are informed.")
    elif status == 2:   # Pending             
        return HttpResponseAccepted()
    elif status == 3:   # Does not exists
        raise HttpResponseNotFoundAnswer()

@login_required
@csrf_exempt
@require_GET
def job_create(request, graph_id, job_kind):
    '''
        Starts a job of the given kind for the given graph.
        It is intended to return immediately with job information for the frontend.
    '''
    job = common.job_create(request.user, graph_id, job_kind)
    response = HttpResponse(status=201)
    response['Location'] = reverse('frontend_job_status', args=[job.pk])
    return response

@login_required
@csrf_exempt
@require_ajax
@require_GET
def graph_transfers(request, graph_id):
    """
    Function: graph_transfers

    Returns a list of transfers for the given graph

    Request Parameters: graph_id = <INT>
    Response:           200 - <TRANSFERS_AS_JSON>

    Parameters:
     {HTTPRequest} request  - the django request object
     {int}         graph_id - the id of the graph to get the transfers for

    Returns:
     {HTTPResponse} a django response object
    """
    transfers = []
    if request.user.is_staff:
        graph     = get_object_or_404(Graph, pk=graph_id)
    else:
        graph     = get_object_or_404(Graph, pk=graph_id, owner=request.user, deleted=False)        

    if graph.kind in ['faulttree', 'fuzztree']:
        for transfer in Graph.objects.filter(~Q(pk=graph_id), owner=request.user, kind=graph.kind, deleted=False):
            transfers.append({'id': transfer.pk, 'name': transfer.name})

    return HttpResponse(json.dumps({'transfers': transfers}), 'application/javascript', status=200)

@login_required
@csrf_exempt
@require_ajax
@require_POST
@never_cache
def nodes(request, graph_id):
    """
    Function: nodes
    
    This function creates a new node in the graph with the provided id. In order to be able to create the node four data
    items about the node are needed: its kind, its position (x and y coordinate) and an id as assigned by the client
    (calculated by the client to prevent waiting for round-trip). The response contains the JSON serialized
    representation of the newly created node and its new location URI.
    
    Request Parameters: client_id = <INT>, kind = <NODE_TYPE>, x = <INT>, y = <INT>
    Response:           201 - <NODE_AS_JSON>, Location = <NODE_URI>
    
    Parameters:
     {HTTPRequest} request   - the django request object
     {int}         graph_id  - the id of the graph where the node shall be added
    
    Returns:
     {HTTPResponse} a django response object
    """
    POST = request.POST
    if request.user.is_staff:
        graph = get_object_or_404(Graph, pk=graph_id)
    else:
        graph = get_object_or_404(Graph, pk=graph_id, owner=request.user, deleted=False)
    try:
        if graph.read_only:
            raise HttpResponseForbiddenAnswer('Trying to create a node in a read-only graph')

        kind = POST['kind']
        assert(kind in notations.by_kind[graph.kind]['nodes'])

        command = commands.AddNode.create_from(graph_id=graph_id, node_id=POST['id'],
                                               kind=kind, x=POST['x'], y=POST['y'], properties=json.loads(POST['properties']))
        command.do()
        node = command.node

        response = HttpResponse(node.to_json(), 'application/javascript', status=201)
        response['Location'] = reverse('node', args=[node.graph.pk, node.pk])
        return response

    # a int conversion of one of the parameters failed or kind is not supported by the graph
    except (ValueError, AssertionError, KeyError):
        raise HttpResponseBadRequestAnswer()

    # the looked up graph does not exist
    except ObjectDoesNotExist:
        raise HttpResponseNotFoundAnswer()

    # should never happen, but for completeness enlisted here
    except MultipleObjectsReturned:
        raise HttpResponseServerErrorAnswer()


@login_required
@csrf_exempt
@require_ajax
@require_POST
@never_cache
def nodegroups(request, graph_id):        

    if request.user.is_staff:
        graph = get_object_or_404(Graph, pk=graph_id)
    else:
        graph = get_object_or_404(Graph, pk=graph_id, owner=request.user, deleted=False)
    if graph.read_only:
        raise HttpResponseForbiddenAnswer('Trying to create a node in a read-only graph')

    nodeids = json.loads(request.POST['nodeIds'])
    client_id = request.POST['id']
    group = NodeGroup(client_id = client_id, graph=graph)
    group.save()        # Prepare ManyToMany relationship
    for nodeid in nodeids:
        try:
            # The client may refer to nodes that are already gone,
            # we simply ignore them
            node = Node.objects.get(pk = nodeid, deleted = False)
            group.nodes.add(node)
        except:
            pass
    group.save()    

    response = HttpResponse(group.to_json(), 'application/javascript', status=201)
    response['Location'] = reverse('nodegroup', args=[graph_id, group.client_id])
    return response

@login_required
@csrf_exempt
@require_ajax
@require_http_methods(['DELETE', 'POST'])
@never_cache
def node(request, graph_id, node_id):
    """
    Function: node
        API handler for all actions on one specific node. This includes changing attributes of a node
        or deleting it.

        Request:            POST 
        Request Parameters: any key-value pairs of attributes that should be changed
        Response:           204 - JSON representation of the node

        Request:            DELETE 
        Request Parameters: none
        Response:           204

    Parameters:
        {HTTPRequest} request   - the django request object
        {int}         graph_id  - the id of the graph where the edge shall be added
        {int}         node_id   - the id of the node that should be changed/deleted

    Returns:
        {HTTPResponse} a django response object
    """
    try:
        node = get_object_or_404(Node, client_id=node_id, graph__pk=graph_id)

        if node.graph.read_only:
            raise HttpResponseForbiddenAnswer('Trying to modify a node in a read-only graph')

        if request.method == 'POST':
            # Interpret all parameters as json. This will ensure correct parsing of numerical values like e.g. ids
            parameters = json.loads(request.POST.get('properties', {}))

            logger.debug('Changing node %s in graph %s to %s' % (node_id, graph_id, parameters))
            command = commands.ChangeNode.create_from(graph_id, node_id, parameters)
            command.do()

            # return the updated node object
            return HttpResponse(node.to_json(), 'application/javascript', status=204)

        elif request.method == 'DELETE':
            command = commands.DeleteNode.create_from(graph_id, node_id)
            command.do()
            return HttpResponse(status=204)

    except Exception as exception:
        logger.error('Exception: ' + str(exception))
        raise exception




@login_required
@csrf_exempt
@require_ajax
@never_cache
def nodegroup(request, graph_id, group_id):
    try:
        group = get_object_or_404(NodeGroup, client_id=group_id, graph__pk=graph_id)

        if group.graph.read_only:
            raise HttpResponseForbiddenAnswer('Trying to modify a node in a read-only graph')

        if request.method == 'DELETE':
            group.deleted = True
            group.save()
            return HttpResponse(status=204)

    except Exception as exception:
        logger.error('Exception: ' + str(exception))
        raise exception



@login_required
@csrf_exempt
@require_ajax
@require_POST
@never_cache
def edges(request, graph_id):
    """
    Function: edges
    
    This API handler creates a new edge in the graph with the given id. The edge links the two nodes 'source' and
    'target' with each other that are provided in the POST body. Additionally, a request to this URL MUST provide
    an id for this edge that was assigned by the client (no wait for round-trip). The response contains the JSON
    serialized representation of the new edge and it location URI.
    
    Request Parameters: client_id = <INT>, source = <INT>, target = <INT>
    Response:           201 - <EDGE_AS_JSON>, Location = <EDGE_URI>
    
    Parameters:
     {HTTPRequest} request   - the django request object
     {int}         graph_id  - the id of the graph where the edge shall be added
    
    Returns:
     {HTTPResponse} a django response object
    """
    POST = request.POST
    try:
        if request.user.is_staff:
            graph = get_object_or_404(Graph, pk=graph_id)
        else:
            graph = get_object_or_404(Graph, pk=graph_id, owner=request.user, deleted=False)
        if graph.read_only:
            raise HttpResponseForbiddenAnswer('Trying to create an edge in a read-only graph')

        command = commands.AddEdge.create_from(graph_id=graph_id, client_id=POST['id'],
                                               from_id=POST['source'], to_id=POST['target'])
        command.do()

        edge = command.edge
        response = HttpResponse(edge.to_json(), 'application/javascript', status=201)
        response['Location'] = reverse('edge', kwargs={'graph_id': graph_id, 'edge_id': edge.client_id})

        return response

    # some values in the request were not parsable
    except (ValueError, KeyError):
        raise HttpResponseBadRequestAnswer()

    # either the graph, the source or the target node are not in the database
    except ObjectDoesNotExist:
        raise HttpResponseNotFoundAnswer("Invalid graph or node ID")

    # should never happen, just for completeness reasons here
    except MultipleObjectsReturned:
        raise HttpResponseServerErrorAnswer()

@login_required
@csrf_exempt
@require_ajax
@require_http_methods(['DELETE', 'POST'])
@never_cache
def edge(request, graph_id, edge_id):
    """
    Function: edge

    This API handler deletes the edge from the graph using the both provided ids. The id of the edge hereby refers to
    the previously assigned client side id and NOT the database id. The response to this request does not contain any
    body.

    Request Parameters: None
    Response:           204

    Parameters:
     {HTTPRequest} request   - the django request object
     {int}         graph_id  - the id of the graph where the edge shall be deleted
     {int}         edge_id   - the id of the edge to be deleted

    Returns:
     {HTTPResponse} a django response object
    """

    try:
        if request.user.is_staff:
            graph = get_object_or_404(Graph, pk=graph_id)
        else:
            graph = get_object_or_404(Graph, pk=graph_id, owner=request.user, deleted=False)

        if graph.read_only:
            raise HttpResponseForbiddenAnswer('Trying to modify an edge in a read-only graph')

        if request.method == 'POST':
            parameters = json.loads(request.POST.get('properties', {}))
            commands.ChangeEdge.create_from(graph_id, edge_id, parameters).do()

            # return the updated node object
            return HttpResponse(status=204)
        if request.method == 'DELETE':
            commands.DeleteEdge.create_from(graph_id=graph_id, edge_id=edge_id).do()
            return HttpResponse(status=204)

    # except ValueError:
    #     raise HttpResponseBadRequestAnswer()

    except ObjectDoesNotExist:
        raise HttpResponseNotFoundAnswer("Invalid edge ID")

    except MultipleObjectsReturned:
        raise HttpResponseServerErrorAnswer()


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def job_files(request, job_secret):
    ''' Allows to retrieve a job input file (GET), or to upload job result files (POST).
        This method is expected to only be used by our backend daemon script, 
        which gets the shared secret as part of the PostgreSQL notification message.
        This reduces the security down to the ability of connecting to the PostgreSQL database,
        otherwise the job URL cannot be determined.
    '''
    job = get_object_or_404(Job, secret=job_secret)
    if request.method == 'GET':
        logger.debug("Delivering data for job %d"%job.pk)
        response = HttpResponse()
        response.content, response['Content-Type'] = job.input_data()
        logger.debug(response.content)
        return response
    elif request.method == 'POST':
        if job.done():
            logger.error("Job already done, discarding uploaded results")
            return HttpResponse() 
        else:
            logger.debug("Storing result data for job %d"%job.pk)
            # Retrieve binary file and store it
            assert(len(request.FILES.values())==1)
            job.result = request.FILES.values()[0].read()
            job.exit_code = 0       # This saves as a roundtrip. Having files means everything is ok.
            job.save()
            if not job.requires_download():
                logger.debug(''.join(job.result))
            return HttpResponse()        

@csrf_exempt
@require_http_methods(['POST'])
def job_exitcode(request, job_secret):
    ''' Allows to set the exit code of a job. 
        This method is expected to only be used by our backend daemon script, 
        which gets the shared secret as part of the PostgreSQL notification message.
        This reduces the security down to the ability of connecting to the PostgreSQL database,
        otherwise the job URL cannot be determined.
    '''
    job = get_object_or_404(Job, secret=job_secret)
    logger.debug("Storing exit code for job %d"%job.pk)
    job.exit_code = request.POST['exit_code']
    job.save()
    return HttpResponse()        

@csrf_exempt
@require_http_methods(['POST'])
def noti_dismiss(request, noti_id):
    """
    Function: noti_dismiss

    API call being used when the user dismisses the notification box on the start (project overview)
    page.
    """
    noti = get_object_or_404(Notification, pk=noti_id)
    noti.users.remove(request.user)
    noti.save()
    return HttpResponse(status=200)

