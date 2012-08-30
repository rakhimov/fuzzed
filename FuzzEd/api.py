from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.urlresolvers import reverse

from django.db import transaction
from django.shortcuts import get_object_or_404

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

# NOTE: it is important to use our custom exceptions!
# 
# REASON: django.http responses are regular returns, transaction.commit_on_success will therefore  
# REASON: always commit changes even if we return errornous responses (400, 404, ...). We can
# REASON: bypass this behaviour by throwing exception that send correct HTTP status to the user 
# REASON: but abort the transaction. The custom exceptions can be found in middleware.py

from FuzzEd.decorators import require_ajax
from FuzzEd.middleware import HttpResponse, HttpResponseBadRequestAnswer, HttpResponseCreated, HttpResponseNotFoundAnswer, HttpResponseServerErrorAnswer
from FuzzEd.models import Graph, Node, Edge, notations, commands

import logging
logger = logging.getLogger('FuzzEd')

try:
    import json
# backwards compatibility with older python versions
except ImportError:
    import simplejson as json

@login_required
@require_ajax
@require_http_methods(['GET', 'POST'])
@csrf_exempt
@transaction.commit_on_success
def graphs(request):
    """
    Function: graphs
    
    This API handler is responsible for all graphes of the user. It operates in two modes: receiving a GET request will return a JSON encoded list of all the graphs of the user. A POST request instead, will create a new graph (requires the below stated parameters) and returns its ID and URI.
    
    Request:            GET - /api/graphs
    Request Parameters: None
    Response:           200 - <GRAPHS_AS_JSON>
                               
    Request:            POST - /api/graphs
    Request Parameters: kind = <GRAPH_KIND>, name = <GRAPH_NAME>
    Response:           201 - Location = <GRAPH_URI>, ID = <GRAPH_ID>
    
    Parameters:
     {HTTPRequest} request  - django request object
                              
    Returns:
     {HTTPResponse} a django response object
    """
    # the user is asking for all of its graphs
    if request.method == 'GET':
        graphs      = Graph.objects.filter(owner=request.user, deleted=False)
        json_graphs = {
            'graphs': [graph.to_dict() for graph in graphs]
        }

        return HttpResponse(json.dumps(json_graphs), 'application/javascript')

    # the request was a post, we are asked to create a new graph
    try:
        # create a graph created command 
        post = request.POST
        commands.AddGraph.create_of(kind=post['kind'], name=post['name'], owner=request.user).do()

        # prepare the response
        graph_id             = command.graph.pk
        response             = HttpResponseCreated()
        response['Location'] = reverse('graph', args=[graph_id])
        response['ID']       = graph_id

        return response

    # something was not right with the request parameters
    except (ValueError, KeyError):
        raise HttpResponseBadRequestAnswer()

    # Should not be reachable, just for error tracing reasons here
    raise HttpResponseServerErrorAnswer()

@login_required
@require_ajax
@require_GET
@csrf_exempt
def graph(request, graph_id):
    """
    Function: graph
    
    The function provides the JSON serialized version of the graph with the provided id given that the graph is owned by the requesting user and it is not marked as deleted.
    
    Request:            GET - /api/graphs/<GRAPH_ID>
    Request Parameters: None
    Response:           200 - <GRAPH_AS_JSON>
    
    Parameters:
     {HTTPRequest} request   - the django request object
     {int}         graph_id  - the id of the graph to be fetched
    
    Returns:
     {HTTPResponse} a django response object
    """
    graph = get_object_or_404(Graph, pk=graph_id, owner=request.user, deleted=False)

    return HttpResponse(graph.to_json(), 'application/javascript')
    
@login_required
@require_ajax
@require_POST
@csrf_exempt
@transaction.commit_on_success
def nodes(request, graph_id):
    """
    Function: nodes
    
    This function creates a new node in the graph with the provided it. In order to be able to create the node four data items about the node are needed: its kind, its position (x and y coordinate) and an id as assigned by the client (calculated by the client to prevent waiting for round-trip). The response contains the JSON serialized representation of the newly created node and its new location URI.
    
    Request:            POST - /api/graphs/<GRAPH_ID>/nodes
    Request Parameters: client_id = <INT>, kind = <NODE_TYPE>, x = <INT>, y = <INT>
    Response:           201 - <NODE_AS_JSON>, Location = <NODE_URI>
    
    Parameters:
     {HTTPRequest} request   - the django request object
     {int}         graph_id  - the id of the graph where the node shall be added
    
    Returns:
     {HTTPResponse} a django response object
    """
    POST = request.POST
    try:
        kind = POST['kind']
        assert(kind in notations.by_kind[graph.kind]['nodes'])

        command = commands.AddNode.create_of(graph_id=graph_id, client_id=POST['id'], \
                                             kind=kind, x=POST['x'], y=POST['y'])
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
@require_ajax
@csrf_exempt
@transaction.commit_on_success
def node(request, graph_id, node_id):
    """
    Delete node from graph stored in the backend
    API Request:  DELETE /api/graphs/[graphID]/nodes/[nodeID], no body
    API Response: no body, status code 204

    Change property of a node
    API Request:            POST /api/graphs/[graphID]/nodes/[nodeID]
    API Request Parameters: key=... , value=...
    API Response:           no body, status code 204

    Change position of a node
    API Request:            POST /api/graphs/[graphID]/nodes/[nodeID]
    API Request Parameters: xcoord=... , ycoord=...
    API Response:           no body, status code 204

    Morph node to another type
    API Request:            POST /api/graphs/[graphID]/nodes/[nodeID]
    API Request Parameters: type=[NODE_TYPE]
    API Response:           no body, status code 204
    """
    if request.is_ajax():
        try:
            g=Graph.objects.get(pk=graph_id, deleted=False)
            n=Node.objects.get(graph=g, client_id=node_id, deleted=False)
        except:
            raise HttpResponseBadRequestAnswer()
        if request.method == 'DELETE':
            # delete node
            try:
                # remove edges explicitly to keep history
                for e in n.outgoing.all():
                    e.deleted=True
                    e.save()
                    c=History(command=Commands.DEL_EDGE, graph=g, edge=e)
                    c.save()
                for e in n.incoming.all():
                    e.deleted=True
                    e.save()
                    c=History(command=Commands.DEL_EDGE, graph=g, edge=e)
                    c.save()
                n.deleted=True
                n.save()
                c=History(command=Commands.DEL_NODE, graph=g, node=n)
                c.save()
            except:
                raise HttpResponseBadRequestAnswer()                        
            else:
                return HttpResponseNoResponse()
        elif request.method == 'POST':
            if 'xcoord' in request.POST and 'ycoord' in request.POST:
                try:
                    oldxcoord=n.xcoord
                    oldycoord=n.ycoord
                    n.xcoord = request.POST['xcoord']
                    n.ycoord = request.POST['ycoord']
                    n.save()
                    c=History(command=Commands.CHANGE_COORD, graph=g, node=n, oldxcoord=oldxcoord, oldycoord=oldycoord)
                    c.save()
                except:
                    raise HttpResponseBadRequestAnswer()
                return HttpResponseNoResponse()
            elif 'key' in request.POST and 'value' in request.POST:
                setNodeProperty(n, request.POST['key'], request.POST['value'])
                return HttpResponseNoResponse()
            elif 'type' in request.POST:
                #TODO change node type          
                return HttpResponseNoResponse()
            else:
                raise HttpResponseBadRequestAnswer()
        raise HttpResponseNotAllowedAnswer(['DELETE','POST'])

@login_required
@require_ajax
@require_POST
@csrf_exempt
@transaction.commit_on_success
def edges(request, graph_id):
    """
    Function: edges
    
    This API handler creates a new edge in the graph with the given id. The edge links the two nodes 'source' and 'destination' with each other that are provided in the POST body. Additionally, a request to this URL MUST provide an id for this edge that was assigned by the client (no wait for round-trip). The response contains the JSON serialized representation of the new edge and it location URI.
    
    Request:            POST - /api/graphs/<GRAPH_ID>/edges
    Request Parameters: client_id = <INT>, source = <INT>, destination = <INT>
    Response:           201 - <EDGE_AS_JSON>, Location = <EDGE_URI>
    
    Parameters:
     {HTTPRequest} request   - the django request object
     {int}         graph_id  - the id of the graph where the edge shall be added
    
    Returns:
     {HTTPResponse} a django response object
    """
    POST = request.POST
    try:
        command = commands.AddEdge.create_of(graph_id=graph_id, client_id=POST['id'], \
                                             from_id=POST['source'], to_id=POST['destination'])
        command.do()

        edge = command.edge
        response = HttpResponse(edge.to_json(), 'application/javascript', status=201)
        response['Location'] = reverse('edge', args[edge.pk])

        return response

    # some values in the request were not parsable
    except (ValueError, KeyError):
        raise HttpResponseBadRequestAnswer()

    # either the graph, the source or the destination node are not in the database
    except ObjectDoesNotExist:
        raise HttpResponseNotFoundAnswer()

    # should never happen, just for completeness reasons here
    except MultipleObjectsReturned:
        raise HttpResponseServerErrorAnswer()

@login_required
@require_ajax
@require_http_methods(['DELETE'])
@transaction.commit_on_success
@csrf_exempt
def edge(request, graph_id, edge_id):
    """
    Function: edge
    
    This API handler deletes the edge from the graph using the both provided ids. The id of the edge hereby referes to the previously assigned client side id and NOT the database id. The response to this request does not contain any body.
    
    Request:            DELETE - /api/graphs/<GRAPH_ID>/edge/<EDGE_ID>
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
        commands.DeleteEdge(graph_id, edge_id).do()
        return HttpResponse(status=204)

    except ValueError:
        raise HttpResponseBadRequestAnswer()

    except ObjectDoesNotExist:
        raise HttpResponseNotFoundAnswer()

    except MultipleObjectsReturned:
        raise HttpResponseServerErrorAnswer()

# TODO: PROVIDE ALL PROPERTIES OF A NODE (/nodes/<id>/properties)
def properties(**kwargs):
    pass

# TODO: PROVIDE THE VALUE OF A PROPERTY WITH GIVEN KEY (/nodes/<id>/properties/<key>)
def property(**kwargs):
    pass

@login_required
@require_ajax
@require_http_methods(["GET", "POST"])
@csrf_exempt
@transaction.commit_on_success
def undos(request, graph_id):
    #
    # TODO: IS NOT WORKING YET
    # TODO: UPDATE DOC STRING
    #
    """
    Fetch undo command stack from backend
    API Request:  GET /api/graphs/[graphID]/undos, no body
    API Response: JSON body with command array of undo stack

    Tell the backend that an undo has been issued in the model
    API Request:  POST /api/graphs/[graphID]/undos, no body
    API Response: no body, status code 204
    """
    if request.method == 'GET':
        #TODO: Fetch undo stack for the graph
        raise HttpResponseNoResponseAnswer()
        
    else:
        #TODO: Perform top command on undo stack
        raise HttpResponseNoResponseAnswer()

@login_required
@require_ajax
@require_http_methods(["GET", "POST"])
@csrf_exempt
@transaction.commit_on_success
def redos(request, graph_id):
    #
    # TODO: IS NOT WORKING YET
    # TODO: UPDATE DOC STRING
    #
    """
    Fetch redo command stack from backend
    API Request:  GET /api/graphs/[graphID]/redos, no body
    API Response: JSON body with command array of redo stack

    Tell the backend that an redo has been issued in the model
    API Request:  POST /api/graphs/[graphID]/redos, no body
    API Response: no body, status code 204
    """
    if request.method == 'GET':
        #TODO Fetch redo stack for the graph
        raise HttpResponseNoResponseAnswer()
    else:
        #TODO Perform top command on redo stack
        raise HttpResponseNoResponseAnswer()