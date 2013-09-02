set(CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

option(VARIADIC_TEMPLATES OFF)

option(USE_INTEL_COMPILER ON)
if (USE_INTEL_COMPILER)
  include(ForceCompiler)
  set(CMAKE_VS_PLATFORM_TOOLSET "Intel C++ Compiler XE 13")
  CMAKE_FORCE_C_COMPILER(icc Intel)
  CMAKE_FORCE_CXX_COMPILER(icpc Intel)
  message(STATUS "Using compiler: ${CMAKE_CXX_COMPILER_ID}")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /Qstd=c++0x")
  message("CMake support for ICC is crappy. Enforce the generation of Visual Studio Projects using this tool: http://software.intel.com/en-us/articles/ICProjConvert100")
endif()

if (APPLE)
  include(ForceCompiler)
  CMAKE_FORCE_C_COMPILER(gcc-4.7 GNU)
  CMAKE_FORCE_CXX_COMPILER(g++-4.7 GNU)
  set(CMAKE_XCODE_ATTRIBUTE_GCC_VERSION "4.7")
endif ()

project(FuzztreeBackends)
cmake_minimum_required(VERSION 2.8.8)
set(CMAKE_MODULE_PATH  ${CMAKE_MODULE_PATH} "${PROJECT_SOURCE_DIR}/cmake")
set(FT_LIB_DIR "${PROJECT_SOURCE_DIR}/lib")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${FT_LIB_DIR})
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELEASE ${FT_LIB_DIR})
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${FT_LIB_DIR})
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_DEBUG ${FT_LIB_DIR})

if ("${CMAKE_CXX_COMPILER_ID}" STREQUAL "Clang")
  # TODO
elseif ("${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pedantic -std=c++0x -fPIC -fexceptions")
  set(Boost_USE_STATIC_LIBS OFF)
elseif ("${CMAKE_CXX_COMPILER_ID}" STREQUAL "Intel")
  # using Intel C++
  message(STATUS "using intel")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /Qstd=c++0x")
elseif ("${CMAKE_CXX_COMPILER_ID}" STREQUAL "MSVC")
  if(CMAKE_CXX_FLAGS MATCHES "/W[0-4]")
    string(REGEX REPLACE "/W[0-4]" "/W4" CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}")
  else()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /W4")
  endif()
  add_definitions(/D_CRT_SECURE_NO_WARNINGS /DNOMINMAX /DWIN32_LEAN_AND_MEAN)
  set(TPN_WIN32 "${TPN_WIN32} /EHsc")
endif()

################# BOOST #################
#########################################

set(Boost_USE_STATIC_LIBS       ON)
set(Boost_USE_MULTITHREADED     ON)
set(Boost_USE_STATIC_RUNTIME    OFF)
add_definitions(-DBOOST_DATE_TIME_NO_LIB -DBOOST_REGEX_NO_LIB)
#add_definitions(-DBoost_DEBUG=1)
add_definitions(-D_ALLOW_KEYWORD_MACROS)

set(BOOST_ROOT $ENV{BOOST_ROOT} CACHE STRING "Set the value of BOOST_ROOT to point to the root folder of your boost install." FORCE)
set(BOOST_INCLUDEDIR ${BOOST_ROOT}/Include)
set(BOOST_LIBRARYDIR ${BOOST_ROOT}/lib)

set(Boost_DIR ${BOOST_ROOT} CACHE STRING "Set the value of BOOST_ROOT to point to the root folder of your boost install." FORCE)
find_package(Boost 1.51.0 COMPONENTS
	regex
	date_time
	system
	filesystem
	program_options
	exception
REQUIRED)

message(STATUS "** Boost Libraries: ${Boost_LIBRARIES}")
find_package(pugixml REQUIRED)


################# XSD ###################
#########################################

find_package(XercesC REQUIRED) # XSD DEPENDS ON ${XERCESC_FOUND}
if(XERCESC_FOUND)
  message(STATUS "Found Xerces-C: ${XERCESC_LIBRARIES}")
  message(STATUS "              : ${XERCESC_INCLUDE_DIR}")
  message(STATUS "       Version: ${XERCESC_VERSION}")
else(XERCESC_FOUND)
  message(FATAL_ERROR "The package Apache Xerces-C++ has not been found")
endif(XERCESC_FOUND)

find_package(Xsd REQUIRED) # CODESYNTHESIS
if(XSD_FOUND)
  message(STATUS "Package CodeSynthesis XSD found: ${XSD_INCLUDE_DIR}")
else(XSD_FOUND)
  message(FATAL_ERROR "The package CodeSynthesis XSD has not been found")
endif(XSD_FOUND)  


############### BEANSTALK ###############
#########################################

option(BUILD_BEANSTALKPP ON)
if (${BUILD_BEANSTALKPP})
  add_subdirectory(thirdParty/beanstalkpp)
  message("Building beanstalkpp")
  set(BEANSTALKPP_LIB "${FT_LIB_DIR}/beanstalkpp")
  set(BEANSTALKPP_INCLUDE thirdParty/beanstalkpp)
else()
  find_package(beanstalkpp REQUIRED)
  message(STATUS "Found Beanstalk Client lib: ${BEANSTALKPP_LIB}")
endif()

############### COMMON ##################
#########################################

include_directories(
	${XERCESC_INCLUDE_DIR}
	${XSD_INCLUDE_DIR}
	${PUGIXML_INCLUDE_DIR}
	${BEANSTALKPP_INCLUDE}
	${Boost_INCLUDE_DIRS}
	${CMAKE_CURRENT_SOURCE_DIR}/thirdParty
	${CMAKE_CURRENT_SOURCE_DIR}/fuzztreeconfiguration
    ${CMAKE_CURRENT_SOURCE_DIR}/common
)

set(COMMON_DIR ${CMAKE_CURRENT_SOURCE_DIR}/common)

set(COMMON_SOURCES
  ${CMAKE_CURRENT_SOURCE_DIR}/common/util.cpp
)

set(COMMON_HEADERS
  ${CMAKE_CURRENT_SOURCE_DIR}/common/platform.h
  ${CMAKE_CURRENT_SOURCE_DIR}/common/util.h
)

############### UNIT TESTS ##############
#########################################

option(BUILD_TESTS OFF)
if (${BUILD_TESTS})
  find_package(gtest REQUIRED)
  add_subdirectory(tests)
  message("Building Tests")
endif()

add_subdirectory(fuzztreeconfiguration)
add_subdirectory(fuzztreeanalysis)
add_subdirectory(simulation)