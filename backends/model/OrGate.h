#pragma once
#include "AbstractNode.h"

class OrGate : public AbstractNode
{
public:
	OrGate(const std::string id) : AbstractNode(id) {};

	void toPetriNet(PetriNet* pn) override { /*TODO*/ };
	const std::string& getTypeDescriptor() override;

};