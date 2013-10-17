#pragma once
#include <boost/filesystem/path.hpp>
#include <boost/program_options.hpp>

/************************************************************************/
/* Parses the command line for an input and output path specification.	*/
/* Exits the application on invalid options								*/
/************************************************************************/

class CommandLineParser
{
public:
	CommandLineParser();
	CommandLineParser(boost::program_options::options_description& additionalOptions);

	const boost::filesystem::path& getInputFilePath() const;
	const boost::filesystem::path& getOutputFilePath() const;
	const boost::filesystem::path& getWorkingDirectory() const;
	const bool& isVerbose() const;

	void parseCommandline(int numArguments, char** arguments);

protected:
	boost::filesystem::path m_inFilePath;
	boost::filesystem::path m_outFilePath;
	boost::filesystem::path m_workingDir;
	bool m_bVerbose;

	boost::program_options::variables_map					m_optionsMap;
	boost::program_options::options_description				m_commands;
};