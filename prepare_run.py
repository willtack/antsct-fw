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
    bids_dir = output_root
    bids_root = output_root / 'bids_dataset'

    # Get relevant container objects
    fw = flywheel.Client(context.get_input('api_key')['key'])
    analysis_container = fw.get(analysis_id)
    project_container = fw.get(analysis_container.parents['project'])
    session_container = fw.get(analysis_container.parent['id'])
    subject_container = fw.get(session_container.parents['subject'])

    project_label = project_container.label

    # inputs
    manual_t1 = context.get_input('t1_anatomy')
    manual_t1_path = None if manual_t1 is None else \
        PosixPath(context.get_input_path('t1_anatomy'))

    logger.info("manual_t1: %s" % manual_t1)
    logger.info("manual_t1_path: %s" % manual_t1_path)

    # configs, use int() to translate the booleans to 0 or 1
    output_prefix = config.get('output-file-root')
    denoise = int(config.get('denoise'))
    num_threads = config.get('num-threads')
    run_quick = int(config.get('run-quick'))
    trim_neck = int(config.get('trim-neck'))
    override = config.get('force-multiple')


def write_command(anat_input, prefix):

    """Create a command script."""
    with flywheel.GearContext() as context:
        cmd = ['/opt/scripts/runAntsCT_nonBIDS.pl',
               '--anatomical-image {}'.format(anat_input),
               '--output-dir {}'.format(gear_output_dir),
               '--output-file-root {}'.format(prefix),
               '--denoise {}'.format(denoise),
               '--num-threads {}'.format(num_threads),
               '--run-quick {}'.format(run_quick),
               '--trim-neck {}'.format(trim_neck)
               ]
    logger.info(' '.join(cmd))
    with antsct_script.open('w') as f:
        f.write(' '.join(cmd))

    return antsct_script.exists()


def fw_heudiconv_download():
    """Use fw-heudiconv to download BIDS data."""
    subjects = [subject_container.label]
    sessions = [session_container.label]

    # Do the download!
    bids_root.parent.mkdir(parents=True, exist_ok=True)
    downloads = export.gather_bids(fw, project_label, subjects, sessions)
    export.download_bids(fw, downloads, str(bids_dir.resolve()), dry_run=False, folders_to_download=['anat'])

    # Use manually specified T1 if it exists
    if manual_t1 is not None:
        anat_input = manual_t1_path
        prefix = 'sub-{}_ses-{}_'.format(subjects[0], sessions[0])
        return True, anat_input, prefix

    layout = BIDSLayout(bids_root)
    anat_list = layout.get(suffix="T1w", extension="nii.gz")

    # Get subject and session label
    # subject_label = layout.get(return_type='id', target='subject')[0].strip("[']")
    # session_label = layout.get(return_type='id', target='session')[0].strip("[']")

    # if there are multiple files or no files, error out
    # if there are multiple files but the user said that was okay, use all of them
    # otherwise just use the one

    if not override and len(anat_list) > 1:
        logger.warning("Multiple anatomical files found in %s. If you want to process multiple images, make sure to select the override config.", bids_root)
        return False
    elif not len(anat_list) or len(anat_list) == 0:
        logger.warning("No anatomical files found in %s", bids_root)
        return False
    elif override and len(anat_list) > 0:
        # Use all found T1s (how am I going to do this?)
        anat_bids_image = anat_list[0]
    else:
        anat_bids_image = anat_list[0]

    anat_input = anat_bids_image.path

    # TODO: set up BIDs filtering (Maybe just for acquisition and run?)
    # filters = {"subject": subjects, "type": 'T1w', extensions:['.nii', '.nii.gz'], return_type: 'file'}
    #
    # if args.session_label:
    #     filters["session"] = args.session_label
    #
    # if args.acquisition_label:
    #     filters["acquisition"] = args.acquisition_label
    #
    # T1w_files = layout.get(filters)

    # Generate prefix from bids layout
    basename = anat_bids_image.filename.split('.')[0]
    prefix = basename.replace('_T1w', '') + '_'

    return True, anat_input, prefix


def main():
    download_ok, anat_input, prefix = fw_heudiconv_download()
    sys.stdout.flush()
    sys.stderr.flush()
    if not download_ok:
        logger.warning("Critical error while trying to download BIDS data.")
        return 1

    command_ok = write_command(anat_input, prefix)
    sys.stdout.flush()
    sys.stderr.flush()
    if not command_ok:
        logger.warning("Critical error while trying to write ANTs-CT command.")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
