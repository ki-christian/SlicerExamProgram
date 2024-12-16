# TODO: Förfina koden
# TODO: Förfina GUI
# TODO: Kontrollera att filen existerar innan laddar in dataset

import logging
import os
from typing import Annotated, Optional

import vtk

import slicer, qt
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)

from slicer import vtkMRMLScalarVolumeNode

import functools

import os
import csv
import re

EXAM_FOLDER_PATH = r"C:\Exam program"
LOCAL_BACKUP_PATH = os.path.join(EXAM_FOLDER_PATH, "Backups")

DATASETS_FILE_NAME = "Exam_program_scene.mrml" #"open_me.mrb"
STUDENT_STRUCTURES_FILE_NAME = "Exams.csv"

BIG_BRAIN = "Big_Brain"
IN_VIVO = "in_vivo"
EX_VIVO = "ex_vivo"

BIG_BRAIN_VOLUME_NAME = "vtkMRMLScalarVolumeNode3"
IN_VIVO_VOLUME_NAME = "vtkMRMLScalarVolumeNode1"
EX_VIVO_VOLUME_NAME = "vtkMRMLScalarVolumeNode2"

NUMBER_OF_QUESTIONS = 10
Q_MESSAGE_BOX_TITLE = "BV4 Exam program"


#
# BV4_STATEX_Grader
#


class BV4_STATEX_Grader(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("BV4_STATEX_Grader")  # TODO: make this more human readable by adding spaces
        # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.categories = ["Basvetenskap 4"]
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Christian Andersson (Karolinska Institutet)"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        # _() function marks text as translatable to other languages
        self.parent.helpText = _("""
Program skapat för stationsexamination i 3D Slicer
i kursen Basvetenskap 4 på Karolinska Institutet.
\nSe mer information i <a href="https://github.com/ki-christian/STATEX/tree/main">dokumentationen</a>.
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _("""
This file was originally developed by Christian Andersson, Karolinska Institutet.
\nchristian.andersson.2@stud.ki.se
""")


#
# BV4_STATEX_GraderParameterNode
#


@parameterNodeWrapper
class BV4_STATEX_GraderParameterNode:
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
# BV4_STATEX_GraderWidget
#


class BV4_STATEX_GraderWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/BV4_STATEX_Grader.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = BV4_STATEX_GraderLogic()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.pushButton_Choose_Mega_Folder.connect("clicked(bool)", self.onChooseMegaFolderButton)
        self.ui.pushButton_Load_Datasets.connect("clicked(bool)", self.onLoadDatasetsButton)
        self.ui.pushButton_Load_Markups.connect("clicked(bool)", self.onLoadMarkupsButton)

        self.ui.pushButton_Structure_1.connect("clicked(bool)", lambda: self.onStructureButton(1))
        self.ui.pushButton_Structure_2.connect("clicked(bool)", lambda: self.onStructureButton(2))
        self.ui.pushButton_Structure_3.connect("clicked(bool)", lambda: self.onStructureButton(3))
        self.ui.pushButton_Structure_4.connect("clicked(bool)", lambda: self.onStructureButton(4))
        self.ui.pushButton_Structure_5.connect("clicked(bool)", lambda: self.onStructureButton(5))
        self.ui.pushButton_Structure_6.connect("clicked(bool)", lambda: self.onStructureButton(6))
        self.ui.pushButton_Structure_7.connect("clicked(bool)", lambda: self.onStructureButton(7))
        self.ui.pushButton_Structure_8.connect("clicked(bool)", lambda: self.onStructureButton(8))
        self.ui.pushButton_Structure_9.connect("clicked(bool)", lambda: self.onStructureButton(9))
        self.ui.pushButton_Structure_10.connect("clicked(bool)", lambda: self.onStructureButton(10))

        self.ui.pushButton_Quit.connect("clicked(bool)", self.onQuitButton)

        # Make sure parameter node is initialized (needed for module reload)
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

    def setParameterNode(self, inputParameterNode: Optional[BV4_STATEX_GraderParameterNode]) -> None:
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

    # choose --> select
    def onChooseMegaFolderButton(self) -> None:
        """Run processing when user clicks "Ladda in strukturer" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            self.ui.lineEdit_Mega_Folder.setText(self.logic.onChooseMegaFolderButtonPressed())

    def onLoadDatasetsButton(self) -> None:
        """Run processing when user clicks "Ladda in strukturer" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            self.logic.onLoadDatasetsButtonPressed(self.ui.lineEdit_Mega_Folder.text)

    def onLoadMarkupsButton(self) -> None:
        """Run processing when user clicks "Ladda in strukturer" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            # Möjligtvis införa printdebugging? Exempelvis: Load Structure Button pressed.
            print("HELLO")
            flip_computer = self.ui.inputBox_Flip_Number.text
            exam_number = self.ui.inputBox_Exam_Number.text

            ret_value = self.logic.onLoadMarkupsButtonPressed(flip_computer, exam_number)
            # Kanske en funktion i logic-klassen med meddelande
            if ret_value != -1:
                # Likaså här
                self.ui.inputBox_Student_Name.setText(self.logic.student_name)
                self.ui.inputBox_Flip_Number.setEnabled(False)
                self.ui.lineEdit_Mega_Folder.setEnabled(False)
                self.ui.inputBox_Exam_Number.setEnabled(False)
                self.ui.pushButton_Structure_1.setText(self.logic.structure_buttons_texts[0])
                self.ui.pushButton_Structure_2.setText(self.logic.structure_buttons_texts[1])
                self.ui.pushButton_Structure_3.setText(self.logic.structure_buttons_texts[2])
                self.ui.pushButton_Structure_4.setText(self.logic.structure_buttons_texts[3])
                self.ui.pushButton_Structure_5.setText(self.logic.structure_buttons_texts[4])
                self.ui.pushButton_Structure_6.setText(self.logic.structure_buttons_texts[5])
                self.ui.pushButton_Structure_7.setText(self.logic.structure_buttons_texts[6])
                self.ui.pushButton_Structure_8.setText(self.logic.structure_buttons_texts[7])
                self.ui.pushButton_Structure_9.setText(self.logic.structure_buttons_texts[8])
                self.ui.pushButton_Structure_10.setText(self.logic.structure_buttons_texts[9])
                self.ui.pushButton_Place_Structure_1.setText(self.logic.place_structure_buttons_texts[0])
                self.ui.pushButton_Place_Structure_2.setText(self.logic.place_structure_buttons_texts[1])
                self.ui.pushButton_Place_Structure_3.setText(self.logic.place_structure_buttons_texts[2])
                self.ui.pushButton_Place_Structure_4.setText(self.logic.place_structure_buttons_texts[3])
                self.ui.pushButton_Place_Structure_5.setText(self.logic.place_structure_buttons_texts[4])
                self.ui.pushButton_Place_Structure_6.setText(self.logic.place_structure_buttons_texts[5])
                self.ui.pushButton_Place_Structure_7.setText(self.logic.place_structure_buttons_texts[6])
                self.ui.pushButton_Place_Structure_8.setText(self.logic.place_structure_buttons_texts[7])
                self.ui.pushButton_Place_Structure_9.setText(self.logic.place_structure_buttons_texts[8])
                self.ui.pushButton_Place_Structure_10.setText(self.logic.place_structure_buttons_texts[9])

    def onStructureButton(self, number) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            self.logic.onStructureButtonPressed(number)

    def onQuitButton(self) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            ret_value = self.logic.onQuitButtonPressed()
            if ret_value != -1:
                self.ui.inputBox_Exam_Number.text = ""
                self.ui.inputBox_Student_Name.setText("")
                self.ui.inputBox_Flip_Number.setEnabled(True)
                self.ui.lineEdit_Mega_Folder.setEnabled(True)
                self.ui.inputBox_Exam_Number.setEnabled(True)
                self.ui.pushButton_Structure_1.setText(self.logic.structure_buttons_texts[0])
                self.ui.pushButton_Structure_2.setText(self.logic.structure_buttons_texts[1])
                self.ui.pushButton_Structure_3.setText(self.logic.structure_buttons_texts[2])
                self.ui.pushButton_Structure_4.setText(self.logic.structure_buttons_texts[3])
                self.ui.pushButton_Structure_5.setText(self.logic.structure_buttons_texts[4])
                self.ui.pushButton_Structure_6.setText(self.logic.structure_buttons_texts[5])
                self.ui.pushButton_Structure_7.setText(self.logic.structure_buttons_texts[6])
                self.ui.pushButton_Structure_8.setText(self.logic.structure_buttons_texts[7])
                self.ui.pushButton_Structure_9.setText(self.logic.structure_buttons_texts[8])
                self.ui.pushButton_Structure_10.setText(self.logic.structure_buttons_texts[9])
                self.ui.pushButton_Place_Structure_1.setText(self.logic.place_structure_buttons_texts[0])
                self.ui.pushButton_Place_Structure_2.setText(self.logic.place_structure_buttons_texts[1])
                self.ui.pushButton_Place_Structure_3.setText(self.logic.place_structure_buttons_texts[2])
                self.ui.pushButton_Place_Structure_4.setText(self.logic.place_structure_buttons_texts[3])
                self.ui.pushButton_Place_Structure_5.setText(self.logic.place_structure_buttons_texts[4])
                self.ui.pushButton_Place_Structure_6.setText(self.logic.place_structure_buttons_texts[5])
                self.ui.pushButton_Place_Structure_7.setText(self.logic.place_structure_buttons_texts[6])
                self.ui.pushButton_Place_Structure_8.setText(self.logic.place_structure_buttons_texts[7])
                self.ui.pushButton_Place_Structure_9.setText(self.logic.place_structure_buttons_texts[8])
                self.ui.pushButton_Place_Structure_10.setText(self.logic.place_structure_buttons_texts[9])

#
# BV4_STATEX_GraderLogic
#


class BV4_STATEX_GraderLogic(ScriptedLoadableModuleLogic):
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
        self.student_structures_path = ""

        self.exam_active = False
        self.structures = []
        self.current_dataset = ""
        self.answered_questions = [False] * NUMBER_OF_QUESTIONS
        self.node = None
        self.flip_computer = 1
        self.student_name = ""
        self.exam_nr = 0
        self.filename = ""
        self.structure_buttons_texts = [""] * NUMBER_OF_QUESTIONS
        self.setStructureButtonsText()
        self.place_structure_buttons_texts = [""] * NUMBER_OF_QUESTIONS
        self.setPlaceStructureButtonsText()

    def getParameterNode(self):
        return BV4_STATEX_GraderParameterNode(super().getParameterNode())

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

    def reset(self):
        self.exam_active = False
        self.structures = []
        self.current_dataset = ""
        self.answered_questions = [False] * NUMBER_OF_QUESTIONS
        self.node = None
        self.student_name = ""
        self.exam_nr = 0
        self.filename = ""

    def setPaths(self, mega_folder_path):
        self.mega_folder_path = mega_folder_path
        self.dataset_path = os.path.join(os.path.join(self.mega_folder_path, "BV4"), "Dataset")
        self.mega_markup_path = os.path.join(os.path.join(os.path.join(self.mega_folder_path, "BV4"), "Examination"), "Markups")
        self.student_structures_path = os.path.join(os.path.join(os.path.join(self.mega_folder_path, "BV4"), "Examination"), "Exams")
        if not os.path.isdir(LOCAL_BACKUP_PATH):
            os.makedirs(LOCAL_BACKUP_PATH)

    # kan nog byta till onChooseFolderButtonPressed
    def onChooseMegaFolderButtonPressed(self):
        folder = str(qt.QFileDialog.getExistingDirectory())
        return folder

    def onLoadDatasetsButtonPressed(self, mega_folder_path):
        self.setPaths(mega_folder_path)
        slicer.util.loadScene(os.path.join(self.dataset_path, DATASETS_FILE_NAME))

    # Accepterar input med meddelandet prompt i range low (inklusive) till high (inklusive)
    def inputNumberInRange(self, prompt, low, high, exceptions=list()):
        while True:
            try:
                value = int(input(prompt))
            except:
                # Kunde ej parse:a input
                print(f"Skriv in en siffra {low}-{high}")
                continue
            if (value >= low and value <= high) or value in exceptions:
                return value
            else:
                print(f"Skriv in en siffra {low}-{high}")

    def onLoadMarkupsButtonPressed(self, flip_computer, exam_nr):
        if self.exam_active:
            qt.QMessageBox.warning(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE,
                                   f"Kan ej ladda in strukturer medan en exam är aktiv.")
            return -1
        try:
            flip_computer = int(flip_computer)
            if flip_computer < 1 or flip_computer > 17: # 17 --> AMOUNT_FLIP_COMPUTERS
                raise ValueError("flip_computer needs to be a number between 1 and 17.")
        except:
            qt.QMessageBox.warning(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE,
                                   f"Ange ett nummer för flipdatorn mellan 1 och 17.")
            return -1
        self.flip_computer = int(flip_computer)
        self.exam_nr = exam_nr
        self.retrieveStructures(exam_nr)

        markup_regex = re.compile(f'({exam_nr})_(.*)(.mrk.json)')
        matching_files = []

        subdirectories = [x[0] for x in os.walk(self.mega_markup_path)]
        for subdirectory in subdirectories:
            for file in os.listdir(subdirectory):
                if markup_regex.match(file):
                    matching_files.append({"filename": file, "room_path": subdirectory})

        if len(matching_files) == 0:
            qt.QMessageBox.information(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE,
                                   f"En markupfil kunde ej hittas för exam nr: {exam_nr}\nFörsök igen senare")
            return -1
        elif len(matching_files) == 1:
            grade_option = 0
        else:
            qt.QMessageBox.information(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE,
                                       f"Det finns fler än en fil med exam nr: {exam_nr}\nVälj i konsolen vilken du vill rätta.")
            for index, file in enumerate(matching_files):
                print(f"{index + 1}: {file.get('filename')}")
            grade_option = self.inputNumberInRange("\nVilken vill du rätta?\n", 1, len(matching_files)) - 1

        # Markups finns sparade på filename
        file = matching_files[grade_option]
        filename = file["filename"]
        room_path = file["room_path"]
        self.student_name = markup_regex.search(filename).group(2)
        self.node = self.loadNodeFromFile(os.path.join(room_path, filename))
        # if os.path.isfile(os.path.join(MARKUP_PATH, filename)):
        self.updateAnsweredQuestions()

        qt.QMessageBox.information(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE,
                                   f"Namn: {self.student_name}\nExam nr: {self.exam_nr}")

        self.exam_active = True
        self.setStructureButtonsText(structures=self.structures)
        self.updateAnsweredQuestions()
        self.setPlaceStructureButtonsText()
        return 0

    def onStructureButtonPressed(self, number):
        if not self.exam_active:
            return -1
        self.updateAnsweredQuestions()
        self.changeDataset(self.structures[number - 1]["Dataset"])
        slicer.modules.markups.logic().JumpSlicesToLocation(0, 0, 0, True)
        self.node.GetDisplayNode().SetActiveControlPoint(number - 1)
        if self.checkIfControlPointExists(number):
            self.centreOnControlPoint(self.node, number - 1, self.structures[number - 1]["Dataset"])

    def onQuitButtonPressed(self):
        # Återställer fönstrena och byter till big brain vid ny användare
        if not self.exam_active:
            qt.QMessageBox.warning(slicer.util.mainWindow(), Q_MESSAGE_BOX_TITLE,
                                   f"Kan inte avsluta när ingen exam pågår.")
            return -1
        slicer.mrmlScene.RemoveNode(self.node)
        self.resetWindow()
        self.resetAnsweredQuestions()
        self.reset()
        self.setStructureButtonsText()
        self.setPlaceStructureButtonsText()

    def setStructureButtonsText(self, structures=None):
        # texts --> strings?
        for i in range(len(self.structure_buttons_texts)):
            if structures is None:
                structure_str = f"Struktur {i + 1}"
            else:
                structure_str = f"Struktur {i + 1}: {structures[i]['Structure']} i {structures[i]['Dataset']}"
            self.structure_buttons_texts[i] = structure_str

    def setPlaceStructureButtonsText(self):
        for i in range(len(self.place_structure_buttons_texts)):
            if not self.exam_active:
                structure_str = ""
            elif self.answered_questions[i]:
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
        self.changeDataset(BIG_BRAIN)
        slicer.modules.markups.logic().JumpSlicesToLocation(0, 0, 0, True)

    # Öppnar csv-filen med strukturer och läser in alla rader tillhörande exam_nr
    def retrieveStructures(self, exam_nr) -> list:
        structures = []
        with open(os.path.join(self.student_structures_path, STUDENT_STRUCTURES_FILE_NAME), encoding="utf-8") as file:
            reader = csv.DictReader(file, delimiter=";")
            for row in reader:
                if row["exam_nr"] == exam_nr:
                    structures.append(row)
        self.structures = structures
        # Kan kanske ta bort return
        return structures

    # Ändrar nuvarande dataset till specificerat dataset
    def changeDataset(self, dataset):
        if dataset.lower()  == BIG_BRAIN.lower():
            self.displaySelectVolume(BIG_BRAIN_VOLUME_NAME)
            self.current_dataset = BIG_BRAIN
        elif dataset.lower() == IN_VIVO.lower():
            self.displaySelectVolume(IN_VIVO_VOLUME_NAME)
            self.current_dataset = IN_VIVO
        elif dataset.lower() == EX_VIVO.lower():
            self.displaySelectVolume(EX_VIVO_VOLUME_NAME)
            self.current_dataset = EX_VIVO
        else:
            print(f"\nDataset: {dataset} existerar ej\n")

    def checkIfControlPointExists(self, question_number):
        # Kan också kolla om den är set eller unset
        return self.answered_questions[question_number - 1]

    # Centrerar vyerna på control point
    # Hantera på ett bättre sätt i framtiden
    def centreOnControlPoint(self, node, index, dataset):
        controlPointCoordinates = node.GetNthControlPointPosition(index) # eller GetNthControlPointPositionWorld
        slicer.modules.markups.logic().JumpSlicesToLocation(controlPointCoordinates[0], controlPointCoordinates[1], controlPointCoordinates[2], True)

    def resetAnsweredQuestions(self):
        self.answered_questions = [False] * NUMBER_OF_QUESTIONS

    def updateAnsweredQuestions(self):
        self.resetAnsweredQuestions() # behövs detta?
        for i in range(self.node.GetNumberOfControlPoints()):
            controlPointCoordinates = self.node.GetNthControlPointPosition(i)
            # Kan också kolla om den är set eller unset
            if controlPointCoordinates[0] != 0.0 or controlPointCoordinates[1] != 0.0 or controlPointCoordinates[2] != 0.0:
                # Om koordinater för control point ej är [0.0, 0.0, 0.0] är frågan besvarad
                self.answered_questions[i] = True

    # Laddar in en fil med markups
    def loadNodeFromFile(self, path):
        return slicer.util.loadMarkups(path)

#
# BV4_STATEX_GraderTest
#


class BV4_STATEX_GraderTest(ScriptedLoadableModuleTest):
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
        self.test_BV4_STATEX_Grader1()

    def test_BV4_STATEX_Grader1(self):
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
        inputVolume = SampleData.downloadSample("BV4_STATEX_Grader1")
        self.delayDisplay("Loaded test data set")

        inputScalarRange = inputVolume.GetImageData().GetScalarRange()
        self.assertEqual(inputScalarRange[0], 0)
        self.assertEqual(inputScalarRange[1], 695)

        outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        threshold = 100

        # Test the module logic

        logic = BV4_STATEX_GraderLogic()

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
