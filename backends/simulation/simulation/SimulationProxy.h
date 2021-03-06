#pragma once

#if IS_WINDOWS 
	#pragma warning(push, 3) 
#endif
#include <string>
#include <boost/filesystem/path.hpp>
#include <boost/program_options.hpp>
#if IS_WINDOWS 
	#pragma warning(pop)
#endif

#include "Config.h"
#include "platform.h"
#include "ResultStruct.h"

class TopLevelEvent;

/************************************************************************/
/* This class handles the different simulations:						*/
/*	- TimeNET-based														*/
/*	  (no support for PAND, SEQ, MTTF)									*/
/*		- with normal petri net structures only							*/
/*		- with structure formula-annotated conditional transitions		*/
/*	- own Petri Net Simulation Algorithm								*/
/*	  (no support for constant-time eval of structure formulas)			*/
/*		- OpenMP parallelization										*/
/*		- C++11-thread parallelization (slightly slower)				*/
/*	- just outputting the structure formula								*/
/************************************************************************/

class SimulationProxy
{
public:
	// constructor for command line tool
	SimulationProxy(int numArguments, char** arguments);
	void parseCommandline_default(int numArguments, char** arguments);

protected:
	// simulates all configurations from one file
	void simulateAllConfigurations(
		const boost::filesystem::path& input,
		const boost::filesystem::path& output,
		const boost::filesystem::path& workingDir,
		const boost::filesystem::path& logFile);

	SimulationResultStruct simulateFaultTree(
		const std::shared_ptr<TopLevelEvent> ft,
		const boost::filesystem::path& workingDir,
		std::ofstream* logFile);

	SimulationResultStruct runSimulationInternal(
		const boost::filesystem::path& inPath);
	
	unsigned int m_missionTime;
	unsigned int m_simulationTime;
	unsigned int m_numRounds;
	double m_convergenceThresh;
};
