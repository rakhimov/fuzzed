from django.db import models
from django.contrib.auth.models import User

from nodes_config import NODE_TYPES, nodeTypeChoices

GRAPH_TYPE = (
    ( 1, u'Fault Tree'),
    ( 2, u'Fuzz Tree'),	
    ( 3, u'Reliability Block Diagram')
)

GRAPH_JS_TYPE = {
	1: 'faulttree',
	2: 'fuzztree',
	3: 'rbd'
}

COMMAND_TYPE = (
	(1, 'Add graph'),		
	(2, 'Add node'), 		
	(3, 'Add edge'),		
	(4, 'Delete graph'),		
	(5, 'Delete node'), 		
	(6, 'Delete edge')		
)

class Graph(models.Model):
	name = models.CharField(max_length=255)
	owner = models.ForeignKey(User, related_name='graphs')
	deleted = models.BooleanField(default=False)
	type = models.PositiveSmallIntegerField(choices=GRAPH_TYPE)
	def __unicode__(self):
		return self.name
	def dump(self, tree=None, indent=0):
		if not tree:
			root=self.nodes.filter(root=True)[0]
			tree=root.getTreeDict()
			print "Tree dump:"
		print "|"*indent + "-%s (%s)"%(tree['name'], tree['id'])
		if "children" in tree:
			for subtree in tree['children']:
				self.dump(subtree, indent+1)		
		
class Node(models.Model):
	name = models.CharField(max_length=255)
	graph = models.ForeignKey(Graph, null=False, related_name='nodes')
	root = models.BooleanField(default=False)
	deleted = models.BooleanField(default=False)
	type = models.PositiveSmallIntegerField(choices=nodeTypeChoices())
	optional = models.BooleanField(default=False)
	def __unicode__(self):
		if self.type == 1:
			if self.root:
				return self.name+" (root)"
			else:
				return self.name
		else:
			return NODE_TYPES[self.type]['type'] + "_" + str(self.pk)
	def getChildren(self):
		edges=self.outgoing.all().filter(deleted=False)
		if len(edges)>0:
			return [e.dest.getTreeDict() for e in edges]
		else:
			return ''
	def getTreeDict(self):
		if self.name=='':
			d={'id':self.pk,'name':NODE_TYPES[self.type]['name']}
		else:
			d={'id':self.pk,'name':self.name}
		kids=self.getChildren()
		if kids:
			d['children']=kids
		return d

class Edge(models.Model):
	src  = models.ForeignKey(Node, null=False, related_name='outgoing')
	dest = models.ForeignKey(Node, null=False, related_name='incoming')
	deleted = models.BooleanField(default=False)
	def __unicode__(self):
		return str(self.src) + "->" + str(self.dest)

class Property(models.Model):
	node = models.ForeignKey(Node, null=True, related_name='properties')
	edge = models.ForeignKey(Edge, null=True, related_name='properties')
	key = models.CharField(max_length=255)
	val = models.CharField(max_length=255)
	deleted = models.BooleanField(default=False)
	def __unicode__(self):
		if self.node:
			return "Node "+str(node)+":%s = %s"%(self.key, self.val)
		else:
			return "Edge "+str(node)+":%s = %s"%(self.key, self.val)

class History(models.Model):
	command = models.PositiveSmallIntegerField(choices=COMMAND_TYPE, null=False)
	graph = models.ForeignKey(Graph, null=False, related_name='commands')
	node = models.ForeignKey(Node, null=True)
	edge = models.ForeignKey(Edge, null=True)
	insert_date = models.DateTimeField(null=False, blank=False, auto_now_add=True, editable=False)
