from __future__ import print_function, division
import contextlib
from itertools import izip, product
import os

import conda_build.conda_interface
import conda_build.api
import yaml


def load_platforms(platforms_dir):
    platforms = []
    for f in os.listdir(platforms_dir):
        if f.endswith('.yml'):
            with open(os.path.join(platforms_dir, f)) as buff:
                platforms.append(yaml.load(buff))
    return platforms


@contextlib.contextmanager
def set_conda_env_vars(env_dict):
    backup_dict = {}
    for env_var, value in env_dict.items():
        backup_dict[env_var] = os.environ.get(env_var)
        if isinstance(value, list):
            value = value[0]
        if not value:
            value = ""
        os.environ[env_var] = value

    yield

    for env_var, value in backup_dict.items():
        if not value:
            del os.environ[env_var]
        else:
            os.environ[env_var] = value


def _filter_environment_with_metadata(build_recipe, version_dicts):
    def del_key(version_dicts, key):
        if key == 'python':
            key = 'py'
        elif key == 'numpy':
            key = 'npy'
        elif key == 'r-base':
            key = 'r'
        del version_dicts['CONDA_' + key.upper()]
        return version_dicts

    with set_conda_env_vars(version_dicts):
        metadata, _, _ = conda_build.api.render(build_recipe)

    for name in ('numpy', 'python', 'perl', 'lua', 'r-base'):
        for req in metadata.get_value('requirements/run'):
            if hasattr(req, 'encode'):
                req = req.encode('utf-8')
            req_parts = req.split(' ')
            if req_parts[0] == name:
                # logic here: if a version is provided, then ignore the build matrix - except
                #   numpy.  If numpy has x.x, that is the only way that it is considered part
                #   of the build matrix.
                #
                # Break = keep the recipe (since we don't fall through to del_key for this name)
                if len(req_parts) > 1:
                    if name == 'numpy' and 'x.x' in req_parts:
                        break
                    # we have a version specified for something other than numpy.  This means
                    #    we are overriding our build matrix.  Do not consider this variable.
                    else:
                        continue
                # fall through for numpy when it does not have any associated x.x
                if name == 'numpy':
                    continue
                break
        else:
            version_dicts = del_key(version_dicts, name)

    return version_dicts


def _get_versions_product(build_recipe, versions_file):
    with open(versions_file) as f:
        dicts = yaml.load(f)
    if os.path.isdir(build_recipe):
        dicts = _filter_environment_with_metadata(build_recipe, dicts)
    # http://stackoverflow.com/a/5228294/1170370
    return (dict(izip(dicts, x)) for x in product(*dicts.itervalues()))


def expand_build_matrix(build_recipe, repo_base_dir, label):
    configurations = []
    if not os.path.isabs(build_recipe):
        build_recipe = os.path.join(repo_base_dir, build_recipe)
    version_sets = _get_versions_product(build_recipe,
                                         os.path.join(repo_base_dir,
                                                      'versions.yml'))
    for version_set in version_sets:
        version_set["TARGET_PLATFORM"] = label,
        if os.path.isdir(build_recipe):
            version_set["BUILD_RECIPE"] = build_recipe
        configurations.append({'variables': version_set})

    return configurations