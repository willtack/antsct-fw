#!/usr/local/miniconda/bin/python
import sys
import logging
from zipfile import ZipFile
from pathlib import PosixPath
from fw_heudiconv.cli import export
from bids import BIDSLayout
import flywheel

# logging stuff
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('antsct-gear')
logger.info("=======: ANTs Cortical Thickness :=======")

# Gather variables that will be shared across functions
with flywheel.GearContext() as context:
    # Setup basic logging
    context.init_logging()
    # Log the configuration for this job
    # context.log_config()
    config = context.config
    analysis_id = context.destination['id']
    gear_output_dir = PosixPath(context.output_dir)
    antsct_script = gear_output_dir / "antsct_run.sh"
    output_root = gear_output_dir / analysis_id
    working_dir = PosixPath(str(output_root.resolve()) + "_work")
    input_dir = PosixPath(context.input_dir)
    bids_root = input_dir / 'bids_dataset'

    # Get image version
    ant_version = '0.1.0'

    # Get relevant container objects
    fw = flywheel.Client(context.get_input('api_key')['key'])
    analysis_container = fw.get(analysis_id)
    project_container = fw.get(analysis_container.parents['project'])
    session_container = fw.get(analysis_container.parent['id'])
    subject_container = fw.get(session_container.parents['subject'])

    project_label = project_container.label

    # Get subject and session label
    layout = BIDSLayout(bids_root)
    subject_label = layout.get(return_type='id', target='subject')[0].strip("[']")
    session_label = layout.get(return_type='id', target='session')[0].strip("[']")

    # configs
    denoise = int(config.get('denoise'))
    num_threads = config.get('num-threads')
    run_quick = int(config.get('run-quick'))
    trim_neck = int(config.get('trim-neck'))

    # output zips
    results_zipfile = gear_output_dir / (analysis_id + "_antsct_results.zip")
    # debug_derivatives_zipfile = gear_output_dir / (
    #     analysis_id + "_debug_qsiprep_derivatives.zip")
    # working_dir_zipfile = gear_output_dir / (analysis_id + "_qsiprep_workdir.zip")
    # errorlog_zipfile = gear_output_dir / (analysis_id + "_qsiprep_errorlog.zip")


def write_command():
    """Create a command script."""
    with flywheel.GearContext() as context:
        cmd = ['/opt/scripts/runAntsCT.py',
               '--bids-directory {}'.format(bids_root),
               '--output-dir {}'.format(output_root),
               '--output-file-root sub-{}_ses-{}'.format(subject_label, session_label),
               '--denoise {}'.format(denoise),
               '--num-threads {}'.format(num_threads),
               '--run-quick {}'.format(run_quick),
               '--trim-neck {}'.format(trim_neck)
               ]
    logger.info(' '.join(cmd))
    with antsct_script.open('w') as f:
        f.write(' '.join(cmd))

    return antsct_script.exists()


# def get_external_bids(scan_info, local_file):
#     """Download an external T1 or T2 image.
#     Query flywheel to find the correct acquisition and get its BIDS
#     info. scan_info came from context.get_input('*_anatomy').
#     """
#     modality = scan_info['object']['modality']
#     logger.info("Adding additional %s folder...", modality)
#     external_acq = fw.get(scan_info['hierarchy']['id'])
#     external_niftis = [f for f in external_acq.files if
#                        f.name == scan_info['location']['name']]
#     if not len(external_niftis) == 1:
#         raise Exception("Unable to find location for extra %s" % modality)
#     nifti = external_niftis[0]
#     nifti_bids_path = bids_root / nifti.info['BIDS']['Path']
#     json_bids_path = str(nifti_bids_path).replace(
#         "nii.gz", ".json").replace(".nii", ".json")
#     # Warn if overwriting: Should never happen on purpose
#     if nifti_bids_path.exists():
#         logger.warning("Overwriting current T1w image...")
#     # Copy to / overwrite its place in BIDS
#     local_file.replace(nifti_bids_path)
#
#     # Download the sidecar
#     export.download_sidecar(nifti.info, json_bids_path)
#     assert PosixPath(json_bids_path).exists()
#     assert nifti_bids_path.exists()


def fw_heudiconv_download():
    """Use fw-heudiconv to download BIDS data."""
    subjects = [subject_container.label]
    sessions = [session_container.label]

    # Do the download!
    bids_root.parent.mkdir(parents=True, exist_ok=True)
    downloads = export.gather_bids(fw, project_label, subjects, sessions)
    export.download_bids(fw, downloads, str(input_dir.resolve()), dry_run=False)

    # Download the extra T1w or T2w
    # if extra_t1 is not None:
    #     get_external_bids(extra_t1, extra_t1_path)
    # if extra_t2 is not None:
    #     get_external_bids(extra_t2, extra_t2_path)

    return True


def create_derivatives_zip(failed):
    output_fname = results_zipfile
    derivatives_files = list(output_root.glob("**/*"))
    with ZipFile(str(output_fname), "w") as zipf:
        for derivative_f in derivatives_files:
            zipf.write(str(derivative_f),
                       str(derivative_f.relative_to(output_root)))


# def create_workingdir_zip():
#     working_files = list(working_dir.glob("**/*"))
#     with ZipFile(str(working_dir_zipfile), "w") as zipf:
#         for working_f in working_files:
#             zipf.write(str(working_f),
#                        str(working_f.relative_to(working_dir)))


def main():
    download_ok = fw_heudiconv_download()
    sys.stdout.flush()
    sys.stderr.flush()
    if not download_ok:
        logger.warning("Critical error while trying to download BIDS data.")
        return 1

    command_ok = write_command()
    sys.stdout.flush()
    sys.stderr.flush()
    if not command_ok:
        logger.warning("Critical error while trying to write ANTs-CT command.")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
