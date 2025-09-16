"""."""

from typing import Tuple

import pydicom


class DICOMNestedTags:
    """Class with methods to get Nested-Modallity specific DICOM metadata."""

    @staticmethod
    def get_rtstruct_referenced_series_uid(dicom_header: pydicom.FileDataset) -> Tuple[str, str]:
        """Collect Referenced Series UID from RTSTRUCT.

        :param pydicom.FileDataset dicom_header: _description_
        :return Tuple[str, str]: _description_
        """
        value = (
            dicom_header.get("ReferencedFrameOfReferenceSequence")[0]
            .get("RTReferencedStudySequence")[0]
            .get("RTReferencedSeriesSequence")[0]
            .get("SeriesInstanceUID")
        )
        return "ReferencedSeriesUID", str(value)

    @staticmethod
    def get_rtstruct_frame_of_reference_uid(dicom_header: pydicom.FileDataset) -> Tuple[str, str]:
        """Collect Frame of Reference UID from RTSTRUCT.

        :param pydicom.FileDataset dicom_header: _description_
        :return Tuple[str, str]: _description_
        """
        value = dicom_header.get("ReferencedFrameOfReferenceSequence")[0].get("FrameOfReferenceUID")
        return "FrameOfReferenceUID", str(value)

    @staticmethod
    def get_rtstruct_structureset_roi_names(dicom_header: pydicom.FileDataset) -> Tuple[str, str]:
        """Collect ROI Names from RTSTRUCT.

        :param pydicom.FileDataset dicom_header: _description_
        :return Tuple[str, str]: _description_
        """
        value = [roi.get("ROIName", "") for roi in dicom_header.get("StructureSetROISequence")]
        return "StructureSetROINames", str(value)

    @staticmethod
    def get_rtplan_referenced_sop_instance_uid(dicom_header: pydicom.FileDataset) -> Tuple[str, str]:
        """Collect Referenced SOP Instance UID from RTPLAN.

        :param pydicom.FileDataset dicom_header: _description_
        :return Tuple[str, str]: _description_
        """
        value = dicom_header.get("ReferencedStructureSetSequence")[0].get("ReferencedSOPInstanceUID")
        return "ReferencedSOPInstanceUID", str(value)

    @staticmethod
    def get_rtdose_referenced_sop_instance_uid(dicom_header: pydicom.FileDataset) -> Tuple[str, str]:
        """Collect Referenced SOP Instance UID from RTDOSE.

        :param pydicom.FileDataset dicom_header: _description_
        :return Tuple[str, str]: _description_
        """
        value = dicom_header.get("ReferencedRTPlanSequence")[0].get("ReferencedSOPInstanceUID")
        return "ReferencedSOPInstanceUID", str(value)
