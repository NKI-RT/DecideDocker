"""."""

from typing import List, Optional


class Patient:
    """Represents a DICOM patient."""

    def __init__(self, patient_data: dict, patientid: str):
        """DICOM Patient.

        :param dict patient_data: DICOM Patient Metadata
        :param str patientid: Patient ID
        """
        self.data = patient_data
        self.patientid = patientid

    def get_modality(self, modality: str) -> List:
        """Get a specified modality.

        :param str modality: DICOMModality
        :return List: List of the specified modality objects with their metadata
        """
        results = []
        for studyuid, study_data in self.data.get("Studies", {}).items():
            study = Study(study_data, studyuid, self)
            for seriesuid, series_data in study_data.get("Series", {}).items():
                if series_data.get("Modality") == modality:
                    if modality == "CT":
                        results.append(CT(series_data, seriesuid, study))
                    elif modality == "RTSTRUCT":
                        results.append(RTSTRUCT(series_data, seriesuid, study))
                    else:
                        results.append(Series(series_data, seriesuid, study))
        return results


class Study:
    """Represents a DICOM study."""

    def __init__(self, study_data: dict, studyuid: str, patient: Optional[Patient] = None):
        """DICOM Study.

        :param dict study_data: DICOM Study Metadata
        :param str studyuid: DICOM StudyInstanceUID
        :param Optional[Patient] patient: The patient object, defaults to None
        """
        self.data = study_data
        self.studyuid = studyuid
        if patient:
            self.patient = patient


class Series:
    """Base class for a DICOM series."""

    def __init__(self, series_data: dict, seriesinstanceuid: str, study: Optional[Study] = None):
        """DICOM Series.

        :param dict series_data: DICOM Series Metadata
        :param str seriesinstanceuid: DICOM SeriesInstanceUID
        :param Optional[Study] study: The study object, defaults to None
        """
        self.data = series_data
        self.seriesinstanceuid = seriesinstanceuid
        if study:
            self.study = study

    def get_files(self) -> List[str]:
        """Return the Files in this series."""
        files = []
        for _, instance_data in self.data.get("Instances", {}).items():
            files.append(instance_data.get("FilePath", {}))
        return files


class CT(Series):
    """CT Series."""

    def __init__(self, series_data: dict, seriesinstanceuid: str, study: Optional[Study] = None):
        """DICOM CT.

        :param dict series_data: DICOM Series Metadata
        :param str seriesinstanceuid: DICOM SeriesInstanceUID
        :param Optional[Study] study: The study object, defaults to None
        """
        super().__init__(series_data, seriesinstanceuid, study)


class RTDOSE(Series):
    """RTDOSE Series."""

    def __init__(self, series_data: dict, seriesinstanceuid: str, study: Optional[Study] = None):
        """DICOM RTDOSE.

        :param dict series_data: DICOM Series Metadata
        :param str seriesinstanceuid: DICOM SeriesInstanceUID
        :param Optional[Study] study: The study object, defaults to None
        """
        super().__init__(series_data, seriesinstanceuid, study)


class RTSTRUCT(Series):
    """RTSTRUCT Series with CT reference finder."""

    def __init__(self, series_data: dict, seriesinstanceuid: str, study: Optional[Study] = None):
        """DICOM RTSTRUCT.

        :param dict series_data: DICOM Series Metadata
        :param str seriesinstanceuid: DICOM SeriesInstanceUID
        :param Optional[Study] study: The study object, defaults to None
        """
        super().__init__(series_data, seriesinstanceuid, study)

    def get_ct(self):
        """Find the CT series referenced by this RTSTRUCT."""
        ref_uid = self.data.get("ReferencedSeriesUID")
        for uid, series in self.study.data.get("Series", {}).items():
            if uid == ref_uid and series.get("Modality") == "CT":
                return CT(series, uid)
        return None
