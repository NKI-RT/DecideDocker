from decide.paths import LOG_DIR
from decide.utils.logger import setup_logger
from decide.xnat import XNATManager
from decide.dcm import DICOMData
from decide.dcm import ImageValidator
from decide.dcm.image_fixes import interpolate_missing_slices
from decide.dcm import ImageConvertor
from decide.dcm import RTStruct
from decide.mask import MaskPostProcessor
from decide.utils.utils import move_files_to_directory
from pathlib import Path
import tempfile
import re
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# the env variables are:
# os.environ["XNAT_URL"] = ''
# os.environ["XNAT_USER"] = ''
# os.environ["XNAT_PASSWORD"] = ""
# os.environ["XNAT_PROJECT"] = ''

if __name__ == "__main__":
    my_logger = setup_logger(
        "Prepare Structures",
        log_file=LOG_DIR / "get_structures_ready.log",
        level="INFO",
    )
    plastimatch_logger = setup_logger(
        "Plastimatch",
        log_file=LOG_DIR / "plastimatch.log",
        level="INFO",
        log_to_console=False,
    )

    myxnat = XNATManager(load_patients=True, logger=my_logger)

    with myxnat.get_connection():
        for patient_id in myxnat.subject_label_list:
            my_logger.info(f"Started with Patient: {patient_id}")
            with tempfile.TemporaryDirectory() as tempdir:
                tempdir = Path(tempdir)
                # Get Experiment, curretly takes the first experiment, assumes only one exp.
                my_logger.info(f"Getting the first Experiment of Patient: {patient_id}")
                myexperiment = myxnat.get_experiment(patient_id)
                # Download all Scans
                my_logger.info(f"Downloading DICOM data of Patient: {patient_id}")
                (tempdir / patient_id).mkdir(parents=True, exist_ok=True)
                myexperiment.download_dir(tempdir / patient_id)

                # DICOM
                my_logger.info("Collecting DICOM Metadata")
                dcmdata = DICOMData(tempdir / patient_id, logger=my_logger)

                my_logger.info("Cleaning DICOM Data")
                patient_info = dcmdata.get_patient(patient_id)

                rtstruct_list = patient_info.get_modality("RTSTRUCT")
                rtstruct_count = len(rtstruct_list)

                # What if thre are more than 1 RTSTRUCTS with a CT!
                if rtstruct_count > 1:
                    my_logger.warning(
                        f"Found {rtstruct_count} RTSTRUCTS, will consider only one that has an associated CT"
                    )

                for dicom_rtstruct in rtstruct_list:
                    ct = dicom_rtstruct.get_ct()
                    if ct:
                        try:
                            my_logger.info("Cleaning DICOM Data: CT")
                            move_files_to_directory(
                                dicom_rtstruct.get_files(),
                                tempdir / patient_id / "RTSTRUCT",
                            )
                            # More than 1 RTSTRUCT & is it the same CT?

                            move_files_to_directory(
                                ct.get_files(), tempdir / patient_id / "CT"
                            )

                            # Vlidating CT DICOM data, detectes problems early.
                            my_logger.info("CT: Validation Overview")
                            validator = ImageValidator(logger=my_logger)
                            validator.validate_image(tempdir / patient_id / "CT")

                            # Converting to NIfTI, the segmentation model needs it.
                            my_logger.info("Converting CT to nifti")
                            plastimatch_logger.info(
                                f"========== Patinet {patient_id} CT =========="
                            )
                            ImageConvertor.dcm_img_to_nifti_platimatch(
                                tempdir / patient_id / "CT",
                                tempdir / "image" / f"{patient_id}.nii.gz",
                                logger=plastimatch_logger,
                            )

                            # Upload NIfTI Image to XNAT
                            myxnat.delete_resource(myexperiment, "decide_image")
                            myxnat.upload_directory(
                                experiment=myexperiment,
                                resource_label="decide_image",
                                source_dir=tempdir / "image",
                                file_type=".nii.gz",
                            )

                            my_logger.info("Cleaning DICOM Data: RTSTRUCT")
                            # RTSTRUCT
                            rtstruct = RTStruct(
                                rtstruct_path=tempdir / patient_id / "RTSTRUCT",
                                logger=my_logger,
                            )
                            # Find only hte GTVs.
                            gtv_names = [
                                name
                                for name in rtstruct.roi_dict.keys()
                                if re.search(r"\bGTV\w*", name, re.IGNORECASE)
                                and not re.search(r"LUNG", name, re.IGNORECASE)
                            ]
                            my_logger.info(f"GTVs Found: {gtv_names}")

                            rtstruct.prune_rtstruct_rois(gtv_names)
                            rtstruct.save_rtstruct(rtstruct.rtstruct_path)

                            # Make 3D Maks and Combine.
                            with tempfile.TemporaryDirectory() as gtv_temp_dir:
                                my_logger.info("Converting RTSTRUCT to nifti")
                                plastimatch_logger.info(
                                    f"========== Patinet {patient_id} RTSTRUCT =========="
                                )
                                ImageConvertor.dcm_rtstruct_to_nifti_platimatch(
                                    str(rtstruct.rtstruct_path),
                                    str(tempdir / patient_id / "CT"),
                                    output_prefix=gtv_temp_dir,
                                    logger=plastimatch_logger,
                                )

                                for roi_mask in Path(gtv_temp_dir).iterdir():
                                    interpolate_missing_slices(
                                        roi_mask, roi_mask, my_logger
                                    )

                                MaskPostProcessor.combine_binary_masks(
                                    [i for i in Path(gtv_temp_dir).iterdir()],
                                    tempdir / "gtvs" / "gtv_total.nii.gz",
                                )

                            # Upload NIfTI GTV to XNAT
                            myxnat.delete_resource(myexperiment, "decide_gtvs")
                            myxnat.upload_directory(
                                experiment=myexperiment,
                                resource_label="decide_gtvs",
                                source_dir=tempdir / "gtvs",
                                file_type=".nii.gz",
                            )
                            #Stop with the first RTSTRUCT
                            break
                        except Exception as e:
                            my_logger.error(f"Encountered Error [{e}] while processing Patient {patient_id}")
            my_logger.info(f"Done for Patinet {patient_id}")
        my_logger.info("Disconneting from XNAT")
    my_logger.info("All Done")
