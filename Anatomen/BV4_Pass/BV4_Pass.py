import logging
import os
from pathlib import Path
from typing import Annotated, Optional

import vtk
import slicer
import qt
import math
import functools
import csv
import re

from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)

from slicer import vtkMRMLScalarVolumeNode

# Configuration constants
ROOM_NUMBERS = ["601A", "601B", "602A", "602B", "603A", "603B", "604A", "604B", "605A", "605B", "606A", "606B",
                "607A", "607B", "608A", "608B", "609A", "609B", "610A", "610B", "611A", "611B", "612A", "612B"]

DATASETS_FILE_NAME = "open_me.mrb" #"open_me.mrb"
STUDENT_STRUCTURES_FILE_NAME = "Exams.csv"

class SessionType:
    INTRO = "INTRO"
    MOTORIK = "MOTORIK"
    SENSORIK = "SENSORIK"
    WORKSHOP = "WORKSHOP"


# Dataset and Session Constants
class DatasetType:
    BIG_BRAIN = "Big_Brain"
    IN_VIVO = "in_vivo"
    EX_VIVO = "ex_vivo"


SESSION_FILE_MAP = {
    SessionType.INTRO: "Intro.csv",
    SessionType.MOTORIK: "Motorik.csv",
    SessionType.SENSORIK: "Sensorik.csv",
    SessionType.WORKSHOP: "Workshop.csv"
}

DATASET_MAP = {
    DatasetType.BIG_BRAIN.lower(): ("vtkMRMLScalarVolumeNode3", DatasetType.BIG_BRAIN),
    DatasetType.IN_VIVO.lower(): ("vtkMRMLScalarVolumeNode1", DatasetType.IN_VIVO),
    DatasetType.EX_VIVO.lower(): ("vtkMRMLScalarVolumeNode2", DatasetType.EX_VIVO),
}

# Configuration
STRUCTURES_PER_PAGE = 20 # STRUCTURE_BUTTON_COUNT
Q_MESSAGE_BOX_TITLE = "BV4 Exam program"

#
# BV4_Pass
#


class BV4_Pass(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("BV4_Pass")  # TODO: make this more human readable by adding spaces
        # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.categories = ["Basvetenskap 4"]
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Christian Andersson (Karolinska Institutet)"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        # _() function marks text as translatable to other languages
        self.parent.helpText = _("""
Program skapat för pass i 3D Slicer
i kursen Basvetenskap 4 på Karolinska Institutet.
\nSe mer information i <a href="https://github.com/ki-christian/STATEX/tree/main">dokumentationen</a>.
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _("""
This file was originally developed by Christian Andersson, Karolinska Institutet.
\nchristian.andersson.2@stud.ki.se
""")


#
# BV4_PassParameterNode
#


@parameterNodeWrapper
class BV4_PassParameterNode:
    """
    The parameters needed by module.

    inputVolume - The volume to threshold.
    imageThreshold - The value at which to threshold the input volume.
    invertThreshold - If true, will invert the threshold.
    thresholdedVolume - The output volume that will contain the thresholded volume.
    invertedVolume - The output volume that will contain the inverted thresholded volume.
    """

    inputVolume: vtkMRMLScalarVolumeNode
    imageThreshold: Annotated[float, WithinRange(-100, 500)] = 100
    invertThreshold: bool = False
    thresholdedVolume: vtkMRMLScalarVolumeNode
    invertedVolume: vtkMRMLScalarVolumeNode


#
# BV4_PassWidget
#


class BV4_PassWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None

    def setupStructureButtons(self):
        for i in range(1, STRUCTURES_PER_PAGE + 1):
            getattr(self.ui, f"pushButton_Structure_{i}").connect("clicked(bool)",
                                                                  lambda _, i=i: self.onStructureButton(i))
            getattr(self.ui, f"pushButton_Place_Structure_{i}").connect("clicked(bool)",
                                                                        lambda _, i=i: self.onPlaceStructureButton(i))
            getattr(self.ui, f"pushButton_Request_Help_{i}").connect("clicked(bool)",
                                                                     lambda _, i=i: self.onRequestHelpButton(i))

    def loadUI(self):
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/BV4_Pass.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        uiWidget.setMRMLScene(slicer.mrmlScene)

    def setupLogic(self):
        self.logic = BV4_PassLogic()

    def setupObservers(self):
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    def setupButtons(self):
        # button = getattr(self.ui, f"pushButton_Structure_{i}", None)
        # if button:
        #     button.connect("clicked(bool)", lambda _, i=i: self.onStructureButton(i))
        self.ui.pushButton_Load_Datasets.connect("clicked(bool)", self.onLoadDatasetsButton)
        for session in [SessionType.INTRO, SessionType.MOTORIK, SessionType.SENSORIK, SessionType.WORKSHOP]:
            getattr(self.ui, f"pushButton_{session.capitalize()}").connect("clicked(bool)", lambda _,
                                                                                                   s=session: self.onLoadStructuresButton(
                s))
        self.ui.pushButton_Reset_Structures.connect("clicked(bool)", self.onResetStructuresButton)
        self.ui.pushButton_Load_Datasets.connect("clicked(bool)", self.onLoadDatasetsButton)

        for i in range(1, STRUCTURES_PER_PAGE + 1):
            getattr(self.ui, f"pushButton_Structure_{i}").connect("clicked(bool)",
                                                                  lambda _, i=i: self.onStructureButton(i))
            getattr(self.ui, f"pushButton_Place_Structure_{i}").connect("clicked(bool)",
                                                                        lambda _, i=i: self.onPlaceStructureButton(i))
            getattr(self.ui, f"pushButton_Request_Help_{i}").connect("clicked(bool)",
                                                                        lambda _, i=i: self.onRequestHelpButton(i))

        self.ui.pushButton_Go_Backwards.connect("clicked(bool)", self.onBackwardsButton)
        self.ui.pushButton_Go_Forward.connect("clicked(bool)", self.onForwardButton)

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)
        self.loadUI()
        self.setupLogic()
        self.setupObservers()
        self.setupButtons()
        self.initializeParameterNode()

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self) -> None:
        """Called each time the user opens a different module."""
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        """Ensure parameter node exists and observed."""
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self._parameterNode.inputVolume:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if firstVolumeNode:
                self._parameterNode.inputVolume = firstVolumeNode

    def setParameterNode(self, inputParameterNode: Optional[BV4_PassParameterNode]) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

    def _checkCanApply(self, caller=None, event=None) -> None:
        if self._parameterNode and self._parameterNode.inputVolume and self._parameterNode.thresholdedVolume:
            self.ui.applyButton.toolTip = _("Compute output volume")
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.toolTip = _("Select input and output volume nodes")
            self.ui.applyButton.enabled = False

    def updateStructureButtons(self):
        for i in range(STRUCTURES_PER_PAGE):
            getattr(self.ui, f"pushButton_Structure_{i + 1}").setText(self.logic.structure_buttons_texts[i])

    def updatePlaceStructureButtons(self):
        for i in range(STRUCTURES_PER_PAGE):
            getattr(self.ui, f"pushButton_Place_Structure_{i + 1}").setText(self.logic.place_structure_buttons_texts[i])

    def onLoadDatasetsButton(self) -> None:
        """Run processing when user clicks "Ladda in strukturer" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            mega_folder_path = r"C:\Users\Christian\Documents\Tutor"
            self.logic.onLoadDatasetsButtonPressed(mega_folder_path)

    def onLoadStructuresButton(self, session) -> None:
        """Run processing when user clicks "Ladda in strukturer" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            # Möjligtvis införa printdebugging? Exempelvis: Load Structure Button pressed.
            room_number = self.ui.inputBox_Room_Number.text.strip()
            if not room_number:
                qt.QMessageBox.warning(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE, "Ange ett rumsnummer.")
                return

            ret_value = self.logic.onLoadStructuresButtonPressed(session, room_number)
            # Kanske en funktion i logic-klassen med meddelande
            if ret_value == -2:
                qt.QMessageBox.warning(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE, "Ange ett giltigt rumsnummer.")
                return
            if ret_value != -1:
                # Likaså här
                self.updateStructureButtons()
                self.updatePlaceStructureButtons()

    def onResetStructuresButton(self) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            ret_value = self.logic.onResetStructuresButtonPressed()
            if ret_value != -1:
                self.updateStructureButtons()
                self.updatePlaceStructureButtons()

    def onStructureButton(self, number) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            self.logic.onStructureButtonPressed(number)
            self.updateStructureButtons()
            self.updatePlaceStructureButtons()

    def onPlaceStructureButton(self, number) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            self.logic.onPlaceStructureButtonPressed(number)
            self.updateStructureButtons()
            self.updatePlaceStructureButtons()

    def onRequestHelpButton(self, number) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            self.logic.onRequestHelpButtonPressed(number)
            self.updateStructureButtons()
            self.updatePlaceStructureButtons()

    def onBackwardsButton(self) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            self.logic.onBackwardsButtonPressed()
            self.updateStructureButtons()
            self.updatePlaceStructureButtons()

    def onForwardButton(self) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            self.logic.onForwardButtonPressed()
            self.updateStructureButtons()
            self.updatePlaceStructureButtons()

#
# BV4_PassLogic
#


class BV4_PassLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)
        self.mega_folder_path = ""
        self.dataset_path = ""
        self.mega_markup_path = ""
        self.student_structures_path = "C:\Exam program\Slicerpass\Strukturer"

        self.number_of_questions = 0
        self.exam_active = False
        self.structures = []
        self.current_dataset = ""
        self.answered_questions = []
        self.node = None
        self.student_name = ""
        self.page = 0
        self.structure_buttons_texts = [""] * STRUCTURES_PER_PAGE
        self.setStructureButtonsText()
        self.place_structure_buttons_texts = [""] * STRUCTURES_PER_PAGE
        self.setPlaceStructureButtonsText()

    def getParameterNode(self):
        return BV4_PassParameterNode(super().getParameterNode())

    def process(self,
                inputVolume: vtkMRMLScalarVolumeNode,
                outputVolume: vtkMRMLScalarVolumeNode,
                imageThreshold: float,
                invert: bool = False,
                showResult: bool = True) -> None:
        """
        Run the processing algorithm.
        Can be used without GUI widget.
        :param inputVolume: volume to be thresholded
        :param outputVolume: thresholding result
        :param imageThreshold: values above/below this threshold will be set to 0
        :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
        :param showResult: show output volume in slice viewers
        """

        if not inputVolume or not outputVolume:
            raise ValueError("Input or output volume is invalid")

        import time

        startTime = time.time()
        logging.info("Processing started")

        # Compute the thresholded output volume using the "Threshold Scalar Volume" CLI module
        cliParams = {
            "InputVolume": inputVolume.GetID(),
            "OutputVolume": outputVolume.GetID(),
            "ThresholdValue": imageThreshold,
            "ThresholdType": "Above" if invert else "Below",
        }
        cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True, update_display=showResult)
        # We don't need the CLI module node anymore, remove it to not clutter the scene with it
        slicer.mrmlScene.RemoveNode(cliNode)

        stopTime = time.time()
        logging.info(f"Processing completed in {stopTime-startTime:.2f} seconds")

    def resetState(self):
        slicer.mrmlScene.RemoveNode(self.node)
        self.current_dataset = ""
        self.resetAnsweredQuestions()
        self.student_name = ""
        self.page = 0

    # KOLLA
    def setPaths(self, mega_folder_path):
        self.mega_folder_path = mega_folder_path
        self.dataset_path = Path(self.mega_folder_path) / "BV4" / "Dataset"
        self.mega_markup_path = Path(self.mega_folder_path) / "BV4" / "Examination" / "Markups"
        self.student_structures_path = Path(self.mega_folder_path) / "Exam program" / "Slicerpass" / "Strukturer"

    def getStructureIndex(self, button_number):
        return button_number + STRUCTURES_PER_PAGE * self.page

    def onLoadDatasetsButtonPressed(self, mega_folder_path):
        self.setPaths(mega_folder_path)
        slicer.util.loadScene(os.path.join(self.dataset_path, DATASETS_FILE_NAME))

    def onLoadStructuresButtonPressed(self, session, room_number):
        if self.exam_active:
            qt.QMessageBox.warning(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE,
                                   f"Kan ej ladda in strukturer medan en exam är aktiv.")
            return -1
        if room_number not in ROOM_NUMBERS:
            return -2
        self.retrieveStructures(1, session=session)
        self.addNodeAndControlPoints(self.structures)
        self.exam_active = True
        print(self.structures)
        self.updateAnsweredQuestions()
        self.number_of_questions = len(self.structures)
        self.answered_questions = [False] * self.number_of_questions
        self.setStructureButtonsText(structures=self.structures)
        self.setPlaceStructureButtonsText()
        return 0

    def onResetStructuresButtonPressed(self):
        # Återställer fönstrena och byter till big brain vid ny användare
        if not self.exam_active:
            qt.QMessageBox.warning(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE,
                                   f"Kan inte spara när ingen exam pågår.")
            return -1
        reply = qt.QMessageBox.question(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE,
                                        f"Är du säker på att du vill avsluta?\nAlla utplacerade markeringar kommer raderas.",
                                        qt.QMessageBox.Yes | qt.QMessageBox.No)
        if reply == qt.QMessageBox.No:
            return -1
        self.resetState()
        self.resetWindow()
        self.addNodeAndControlPoints(self.structures)
        self.setStructureButtonsText(structures=self.structures)
        self.setPlaceStructureButtonsText()

    def onStructureButtonPressed(self, button_number):
        if not self.exam_active:
            return -1
        structure_number = self.getStructureIndex(button_number)
        if structure_number - 1 >= self.number_of_questions: # ÄNDRA DETTA
            return -1
        self.updateAnsweredQuestions()
        self.setPlaceStructureButtonsText()
        self.changeDataset(self.structures[structure_number - 1]["Dataset"])
        slicer.modules.markups.logic().JumpSlicesToLocation(0, 0, 0, True)
        self.node.GetDisplayNode().SetActiveControlPoint(structure_number - 1)
        if self.checkIfControlPointExists(structure_number):
            self.centreOnControlPoint(self.node, structure_number - 1, self.structures[structure_number - 1]["Dataset"])

    def onPlaceStructureButtonPressed(self, button_number):
        if not self.exam_active:
            return -1
        structure_number = self.getStructureIndex(button_number)
        if structure_number - 1 >= self.number_of_questions: # ÄNDRA DETTA
            return -1
        self.updateAnsweredQuestions()
        self.setPlaceStructureButtonsText()
        self.changeDataset(self.structures[structure_number - 1]["Dataset"])
        if self.answered_questions[structure_number - 1]:
            reply = qt.QMessageBox.question(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE,
                                            f"Du har redan placerat ut {self.structures[structure_number - 1]['Structure']}.\nÄr du säker på att du vill placera om den?",
                                            qt.QMessageBox.Yes | qt.QMessageBox.No)
            if reply == qt.QMessageBox.No:
                return -1
        self.setNewControlPoint(self.node, structure_number - 1)

    def onRequestHelpButtonPressed(self, button_number):
        if not self.exam_active:
            return -1
        qt.QMessageBox.warning(slicer.util.mainWindow(), "Hjälp", "Hjälp är på väg!")

    def onBackwardsButtonPressed(self):
        if self.page > 0:
            self.page -= 1
            self.setStructureButtonsText(structures=self.structures, page=self.page)
            self.updateAnsweredQuestions()
            self.setPlaceStructureButtonsText()

    def onForwardButtonPressed(self):
        if self.page < math.floor(len(self.structures)/STRUCTURES_PER_PAGE):
            self.page += 1
            self.setStructureButtonsText(structures=self.structures, page=self.page)
            self.updateAnsweredQuestions()
            self.setPlaceStructureButtonsText()

    def setStructureButtonsText(self, structures=None, page=0):
        # texts --> strings?
        for i in range(0, STRUCTURES_PER_PAGE):
            structure_number = self.getStructureIndex(i)
            if structures is None: # Kan nog flytta ut
                structure_str = f"Struktur {structure_number + 1}"
            elif structure_number >= len(structures):
                structure_str = ""
            else:
                structure_str = f"Struktur {structure_number + 1}: {structures[structure_number]['Structure']} i {structures[structure_number]['Dataset']}"
            self.structure_buttons_texts[i] = structure_str

    def setPlaceStructureButtonsText(self):
        for i in range(len(self.place_structure_buttons_texts)):
            structure_number = self.getStructureIndex(i)
            if not self.exam_active or structure_number >= len(self.structures):
                structure_str = ""
            elif self.answered_questions[structure_number]:
                structure_str = "(✓)"
            else:
                structure_str = "(X)"
            self.place_structure_buttons_texts[i] = structure_str

    def displaySelectVolume(self, a):
        layoutManager = slicer.app.layoutManager()
        for sliceViewName in layoutManager.sliceViewNames():
            view = layoutManager.sliceWidget(sliceViewName).sliceView()
            sliceNode = view.mrmlSliceNode()
            sliceLogic = slicer.app.applicationLogic().GetSliceLogic(sliceNode)
            compositeNode = sliceLogic.GetSliceCompositeNode()
            compositeNode.SetBackgroundVolumeID(str(a))

    # Byter dataset till big brain och fokuserar på koordinaterna [0, 0, 0]
    def resetWindow(self):
        self.changeDataset(DatasetType.BIG_BRAIN)
        slicer.modules.markups.logic().JumpSlicesToLocation(0, 0, 0, True)

    # Öppnar csv-filen med strukturer och läser in alla rader tillhörande exam_nr
    def retrieveStructures(self, exam_nr, session=None) -> list:
        file_name = SESSION_FILE_MAP.get(session, STUDENT_STRUCTURES_FILE_NAME)
        with open(os.path.join(self.student_structures_path, file_name),
                  encoding="utf-8") as file:
            reader = csv.DictReader(file, delimiter=";")
            structures = [row for row in reader if row.get("exam_nr") == str(exam_nr)]
        self.structures = structures
        # Kan kanske ta bort return
        return structures

    # Ändrar nuvarande dataset till specificerat dataset
    def changeDataset(self, dataset: str):
        key = dataset.lower()
        if key in DATASET_MAP:
            volume_name, canonical_name = DATASET_MAP[key]
            self.displaySelectVolume(volume_name)
            self.current_dataset = canonical_name
            logging.info(f"Changed dataset to {canonical_name}")
        else:
            logging.warning(f"Dataset not recognized: {dataset}")
            qt.QMessageBox.warning(
                slicer.util.mainWindow(),
                Q_MESSAGE_BOX_TITLE,
                f"Dataset '{dataset}' är inte giltigt eller saknas."
            )

    # Lägger till en nod med namnet exam_nr och lägger till tillhörande control points
    # för varje struktur i structures. Namnet på varje control point blir strukturens
    # namn och beskrivningen blir vilket nummer strukturen är.
    def addNodeAndControlPoints(self, structures):
        node = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode', f"Strukturer")
        node.SetLocked(1)
        node.AddNControlPoints(len(structures), "", [0, 0, 0])
        for _index, structure in enumerate(structures):
            try:
                index = int(structure["question"]) - 1
            except (KeyError, ValueError):
                index = _index
            node.SetNthControlPointLabel(index, structure["Structure"])
            node.SetNthControlPointDescription(index, f"Struktur {index + 1}")
            node.SetNthControlPointLocked(index, False)
            # Avmarkerar strukturen innan man placerat den.
            # Tar bort koordinater [0, 0, 0] för skapade punkten så att den inte är i vägen.
            node.UnsetNthControlPointPosition(index)
        self.node = node
        return node

    # Ändrar till place mode så att en ny control point kan placeras ut
    def setNewControlPoint(self, node, index):
        # Återställ control point
        node.SetNthControlPointPosition(index, 0.0, 0.0, 0.0)
        node.UnsetNthControlPointPosition(index)
        # Placera ut ny control point
        node.SetControlPointPlacementStartIndex(index)
        slicer.modules.markups.logic().StartPlaceMode(1)
        interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
        # Återgå sedan till normalt läge när klar
        interactionNode.SetPlaceModePersistence(0)
        # interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
        # interactionNode.SwitchToViewTransformMode()

        # also turn off place mode persistence if required
        # interactionNode.SetPlaceModePersistence(0)

    def checkIfControlPointExists(self, question_number):
        # Kan också kolla om den är set eller unset
        return self.answered_questions[question_number - 1]

    # Centrerar vyerna på control point
    # Hantera på ett bättre sätt i framtiden
    def centreOnControlPoint(self, node, index, dataset):
        controlPointCoordinates = node.GetNthControlPointPosition(index)  # eller GetNthControlPointPositionWorld
        slicer.modules.markups.logic().JumpSlicesToLocation(controlPointCoordinates[0], controlPointCoordinates[1],
                                                            controlPointCoordinates[2], True)

    def resetAnsweredQuestions(self):
        self.answered_questions = [False] * self.number_of_questions # ÄNDRA DENNA

    def updateAnsweredQuestions(self):
        self.resetAnsweredQuestions() # behövs detta? Kan annars ta else False
        for i in range(self.node.GetNumberOfControlPoints()):
            controlPointCoordinates = self.node.GetNthControlPointPosition(i)
            # Kan också kolla om den är set eller unset
            if controlPointCoordinates[0] != 0.0 or controlPointCoordinates[1] != 0.0 or controlPointCoordinates[2] != 0.0:
                # Om koordinater för control point ej är [0.0, 0.0, 0.0] är frågan besvarad
                self.answered_questions[i] = True

#
# BV4_PassTest
#


class BV4_PassTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_BV4_Pass1()

    def test_BV4_Pass1(self):
        """Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """

        self.delayDisplay("Starting the test")

        # Get/create input data

        import SampleData

        registerSampleData()
        inputVolume = SampleData.downloadSample("BV4_Pass1")
        self.delayDisplay("Loaded test data set")

        inputScalarRange = inputVolume.GetImageData().GetScalarRange()
        self.assertEqual(inputScalarRange[0], 0)
        self.assertEqual(inputScalarRange[1], 695)

        outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        threshold = 100

        # Test the module logic

        logic = BV4_PassLogic()

        # Test algorithm with non-inverted threshold
        logic.process(inputVolume, outputVolume, threshold, True)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], threshold)

        # Test algorithm with inverted threshold
        logic.process(inputVolume, outputVolume, threshold, False)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], inputScalarRange[1])

        self.delayDisplay("Test passed")
