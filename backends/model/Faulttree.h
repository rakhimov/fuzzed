#pragma once
#include "AbstractModel.h"

class Faulttree : public AbstractModel
{
public:
	// whatever logic is faulttree-specific. MOCUS?

protected:
	void handleBasicEvent(const pugi::xml_node xmlnode, AbstractNode* node) override;

};