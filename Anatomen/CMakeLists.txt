cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(Anatomen)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/Anatomen")
set(EXTENSION_CATEGORY "Slicer_Program")
set(EXTENSION_CONTRIBUTORS "Christian Andersson (Karolinska Institutet)")
set(EXTENSION_DESCRIPTION "This is an example of a simple extension")
set(EXTENSION_ICONURL "https://www.example.com/Slicer/Extensions/Anatomen.png")
set(EXTENSION_SCREENSHOTURLS "https://www.example.com/Slicer/Extensions/Anatomen/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(BV4_STATEX)
add_subdirectory(BV4_STATEX_Student)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
