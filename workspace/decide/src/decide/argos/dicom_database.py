"""
DicomDatabase.py Module - ARGOS-1.

This module originates from the ARGOS-1 project and has been reformatted and refactored by Amal Joseph Varghese,
to comply with the PEP 8 and PEP 257 coding standards required by NKI-RT.

Modifications include:
- Code style improvements for readability and maintainability
- Structural refactoring to align with best practices
- Documentation enhancements for clarity and consistency
"""

from __future__ import annotations

import os

import pydicom


class DicomDatabase:
    """Abstractions for handling DICOM data."""

    def __init__(self):
        """DicomDatabase: Abstractions for handling DICOM data."""
        self.patient = dict()

    def parse_folder(self, folder_path: str):
        """Read metadata of DICOM files form the sorce folder.

        :param str folder_path: the source folder
        """
        for root, _, files in os.walk(folder_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                if file_path.endswith(".dcm") or file_path.endswith(".DCM"):
                    dcm_header = pydicom.dcmread(file_path)
                    patient_id = dcm_header[0x10, 0x20].value
                    patient = self.get_or_create_patient(patient_id)
                    patient.add_file(file_path, dcm_header)

    def get_or_create_patient(self, patient_id: str) -> "Patient":
        """Get or create a Patient object.

        :param str patient_id: Patient ID
        :return Patient: The patient object
        """
        if patient_id not in self.patient:
            self.patient[patient_id] = Patient()
        return self.patient[patient_id]

    def count_patients(self):
        """Returns number of patients in this DicomDatabse object."""
        return len(self.patient)

    def get_patient(self, patient_id: str) -> Patient:
        """Get the patient object given Patient ID.

        :param str patient_id: Patient ID
        :return Patient: The patient object
        """
        return self.patient[patient_id]

    def get_patient_ids(self):
        """List patient IDs from Database."""
        return self.patient.keys()

    def does_patient_exist(self, patient_id: str) -> bool:
        """Check if Patient in Databse.

        :param str patient_id: Patient ID
        :return bool: True if Patient in Database
        """
        return patient_id in self.patient


class Patient:
    """The Patient Class."""

    def __init__(self):
        """Create the Patient object."""
        self.ct = dict()
        self.rtstruct = dict()

    def add_file(self, file_path: str, dcm_header: pydicom.Dataset):
        """Add a DICOM file to this Patient.

        :param str file_path: dicom filepath
        :param pydicom.Dataset dcm_header: DICOM header
        """
        modality = dcm_header[0x8, 0x60].value
        sop_instance_uid = dcm_header[0x8, 0x18].value
        series_instance_uid = dcm_header[0x20, 0xE].value
        if (modality == "CT") or (modality == "PT") or (modality == "MR"):
            if series_instance_uid not in self.ct:
                self.ct[series_instance_uid] = CT()
            my_ct = self.ct[series_instance_uid]
            my_ct.add_ct_slice(file_path)
        if modality == "RTSTRUCT":
            struct = RTStruct(file_path)
            self.rtstruct[sop_instance_uid] = struct

    def count_ct_scans(self):
        """Count CT Scans in this patient."""
        return len(self.ct)

    def count_rtstructs(self):
        """Count RTSTRUCTs in this Patient."""
        return len(self.rtstruct)

    def get_ct_scan(self, series_instance_uid: str) -> "CT":
        """Get the CT Scan given the SeriesInstanceUID.

        :param str series_instance_uid: SeriesInstanceUID
        :return CT: The CT object
        """
        if series_instance_uid is not None:
            if self.does_ct_exist(series_instance_uid):
                return self.ct[series_instance_uid]
        return None

    def get_rtstruct(self, sop_instance_uid: str) -> "RTStruct":
        """Get the RTSTRUCT given the SOPInstanceUID.

        :param str sop_instance_uid: SOPInstanceUID
        :return RTStruct: The RTSTRUCT object
        """
        return self.rtstruct[sop_instance_uid]

    def get_ct_scans(self):
        """Get the SeriesInstacneUIDs of CT scans."""
        return self.ct.keys()

    def get_rtstructs(self):
        """Get the SOPInstacneUIDs of RTSTRUCTs."""
        return self.rtstruct.keys()

    def does_ct_exist(self, series_instance_uid: str) -> bool:
        """Check if a CT series exists for this patient.

        :param str series_instance_uid: SeriesInstacneUID of CT scan
        :return bool: True if the CT exists.
        """
        return series_instance_uid in self.ct

    def does_rtstruct_exist(self, sop_instance_uid: str):
        """Check if a RTSTRUCT exists for this patient.

        :param str sop_instance_uid: SOPInstanceUID
        :return bool: True if the RTSTRUCT exists.
        """
        return sop_instance_uid in self.rtstruct

    def getct_for_rtstruct(self, rtstruct: "RTStruct") -> "CT":
        """Get the related CT scan object for the given RTStruct.

        :param RTStruct rtstruct: The RTStruct object
        :return CT: The related CT Object
        """
        if rtstruct.get_referenced_ct_uid() is not None:
            return self.get_ct_scan(rtstruct.get_referenced_ct_uid())
        else:
            return None


class CT:
    """The CT Class."""

    def __init__(self):
        """Creates the CT object."""
        self.file_path = list()

    def add_ct_slice(self, file_path: str):
        """Add a CT slice to this object.

        :param str file_path: CT slice path
        """
        self.file_path.append(file_path)

    def get_slices(self) -> list:
        """Get the CT Slice filepaths.

        :return list:List of CT slice paths.
        """
        return self.file_path

    def get_slice_count(self):
        """Get CT Slice Count."""
        return len(self.file_path)

    def get_slice_header(self, index: int) -> pydicom.Dataset:
        """Get the pydicom header of the n-th Ct slice.

        :param int index: Index of the CT Slice
        :param pydicom.Dataset dcm_header: DICOM header
        """
        return pydicom.dcmread(self.file_path[index])


class RTStruct:
    """The  RTStruct Class."""

    def __init__(self, file_path: str):
        """Creates the RTStruct object.

        :param str file_path: RTSTRUCT path
        """
        self.file_path = file_path

    def get_header(self) -> pydicom.FileDataset:
        """Get the dicom header.

        :return pydicom.FileDataset: DICOM header
        """
        return pydicom.dcmread(self.file_path)

    def get_referenced_ct_uid(self) -> str:
        """Get the SeriesInstanceUID of referenecd CT.

        :return str: SeriesInstanceUID
        """
        dcm_header = self.get_header()
        if len(list(dcm_header[0x3006, 0x10])) > 0:
            ref_frame_of_ref = (dcm_header[0x3006, 0x10])[0]
            if len(list(ref_frame_of_ref[0x3006, 0x0012])) > 0:
                rt_ref_study = (ref_frame_of_ref[0x3006, 0x0012])[0]
                if len(list(rt_ref_study[0x3006, 0x14])) > 0:
                    rt_ref_serie = (rt_ref_study[0x3006, 0x14])[0]
                    return rt_ref_serie[0x20, 0xE].value
        return None

    def get_file_location(self) -> str:
        """Get the RTSTRUCT filepath.

        :param str file_path: RTSTRUCT path
        """
        return self.file_path
