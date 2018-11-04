# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import sys
import os

import pytest
from docopt import DocoptExit
from scripttest import TestFileEnvironment

import konch


try:
    import ptpython  # noqa: F401
except ImportError:
    HAS_PTPYTHON = False
else:
    HAS_PTPYTHON = True


def assert_in_output(s, res, message=None):
    """Assert that a string is in either stdout or std err.
    Included because banners are sometimes outputted to stderr.
    """
    assert any(
        [s in res.stdout, s in res.stderr]
    ), message or "{0} not in output".format(s)


@pytest.fixture
def env():
    return TestFileEnvironment(ignore_hidden=False)


def teardown_function(func):
    konch.reset_config()


def test_make_banner_custom():
    text = "I want to be the very best"
    result = konch.make_banner(text)
    assert text in result
    assert sys.version in result


def test_full_formatter():
    class Foo(object):
        def __repr__(self):
            return "<Foo>"

    context = {"foo": Foo(), "bar": 42}

    assert (
        konch.format_context(context, formatter="full")
        == "\nContext:\nbar: 42\nfoo: <Foo>"
    )


def test_short_formatter():
    class Foo(object):
        def __repr__(self):
            return "<Foo>"

    context = {"foo": Foo(), "bar": 42}

    assert konch.format_context(context, formatter="short") == "\nContext:\nbar, foo"


def test_custom_formatter():
    context = {"foo": 42, "bar": 24}

    def my_formatter(ctx):
        return "*".join(sorted(ctx.keys()))

    assert konch.format_context(context, formatter=my_formatter) == "bar*foo"


def test_make_banner_includes_full_context_by_default():
    context = {"foo": 42}
    result = konch.make_banner(context=context)
    assert konch.format_context(context, formatter="full") in result


def test_make_banner_hide_context():
    context = {"foo": 42}
    result = konch.make_banner(context=context, context_format="hide")
    assert konch.format_context(context) not in result


def test_make_banner_custom_format():
    context = {"foo": 42}
    result = konch.make_banner(context=context, context_format=lambda ctx: repr(ctx))
    assert repr(context) in result


def test_cfg_defaults():
    assert konch._cfg["shell"] == konch.AutoShell
    assert konch._cfg["banner"] is None
    assert konch._cfg["context"] == {}
    assert konch._cfg["context_format"] == "full"


def test_config():
    assert konch._cfg == konch.Config()
    konch.config({"banner": "Foo bar"})
    assert konch._cfg["banner"] == "Foo bar"


def test_reset_config():
    assert konch._cfg == konch.Config()
    konch.config({"banner": "Foo bar"})
    konch.reset_config()
    assert konch._cfg == konch.Config()


def test_parse_args():
    try:
        args = konch.parse_args()
        assert "--shell" in args
        assert "init" in args
        assert "<config_file>" in args
        assert "--name" in args
    except DocoptExit:
        pass


def test_context_list2dict():
    import math

    class MyClass:
        pass

    def my_func():
        pass

    my_objects = [math, MyClass, my_func]
    expected = {"my_func": my_func, "MyClass": MyClass, "math": math}
    assert konch.context_list2dict(my_objects) == expected


def test_config_list():
    assert konch._cfg == konch.Config()

    def my_func():
        return

    konch.config({"context": [my_func]})
    assert konch._cfg["context"]["my_func"] == my_func


def test_config_converts_list_context():
    import math

    config = konch.Config(context=[math])
    assert config["context"] == {"math": math}


def test_config_set_context_converts_list():
    import math

    config = konch.Config()
    config["context"] = [math]
    assert config["context"] == {"math": math}


def test_config_update_context_converts_list():
    import math

    config = konch.Config()
    config.update({"context": [math]})
    assert config["context"] == {"math": math}


def test_named_config_adds_to_registry():
    assert konch._config_registry["default"] == konch._cfg
    assert len(konch._config_registry.keys()) == 1
    konch.named_config("mynamespace", {"context": {"foo": 42}})
    assert len(konch._config_registry.keys()) == 2
    # reset config_registry
    konch._config_registry = {"default": konch._cfg}


def test_context_can_be_callable():
    def get_context():
        return {"foo": 42}

    shell = konch.Shell(context=get_context)

    assert shell.context == {"foo": 42}


##### Command tests #####


def test_init_creates_config_file(env):
    res = env.run("konch", "init")
    assert res.returncode == 0
    assert konch.CONFIG_FILE in res.files_created


def test_init_with_filename(env):
    res = env.run("konch", "init", "myconfig")
    assert "myconfig" in res.files_created


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_konch_with_no_config_file(env):
    res = env.run("konch", "-f", "notfound", expect_stderr=True, cwd=env.base_path)
    assert res.returncode == 0


def test_konch_init_when_config_file_exists(env):
    env.run("konch", "init")
    res = env.run("konch", "init", expect_error=True)
    assert "already exists" in res.stderr
    assert res.returncode == 1


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_default_banner(env):
    env.run("konch", "init")
    res = env.run("konch", expect_stderr=True)
    assert_in_output(str(sys.version), res)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_config_file_not_found(env):
    res = env.run("konch", "-f", "notfound", expect_stderr=True)
    assert "not found" in res.stderr
    assert res.returncode == 0


TEST_CONFIG = """
import konch

konch.config({
    'banner': 'Test banner',
    'prompt': 'myprompt >>>'
})
"""


@pytest.fixture
def fileenv(request, env):
    fpath = os.path.join(env.base_path, "testrc")
    with open(fpath, "w") as fp:
        fp.write(TEST_CONFIG)

    def finalize():
        os.remove(fpath)

    request.addfinalizer(finalize)
    return env


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_custom_banner(fileenv):
    res = fileenv.run("konch", "-f", "testrc", expect_stderr=True)
    assert_in_output("Test banner", res)


# TODO: Get this test working with IPython
def test_custom_prompt(fileenv):
    res = fileenv.run("konch", "-f", "testrc", "-s", "py", expect_stderr=True)
    assert_in_output("myprompt >>>", res)


def test_version(env):
    res = env.run("konch", "--version")
    assert konch.__version__ in res.stdout
    res = env.run("konch", "-v")
    assert konch.__version__ in res.stdout


TEST_CONFIG_WITH_NAMES = """
import konch

konch.config({
    'context': {
        'foo': 42,
    },
    'banner': 'Default'
})

konch.named_config('conf2', {
    'context': {
        'bar': 24
    },
    'banner': 'Conf2'
})

konch.named_config(['conf3', 'c3'], {
    'context': {
        'baz': 424,
    },
    'banner': 'Conf3',
})
"""


TEST_CONFIG_WITH_SETUP_AND_TEARDOWN = """
import konch

def setup():
    print('setup!')

def teardown():
    print('teardown!')
"""


@pytest.fixture
def names_env(request, env):
    fpath = os.path.join(env.base_path, ".konchrc")
    with open(fpath, "w") as fp:
        fp.write(TEST_CONFIG_WITH_NAMES)

    def finalize():
        os.remove(fpath)

    request.addfinalizer(finalize)
    return env


@pytest.fixture
def setup_env(request, env):
    fpath = os.path.join(env.base_path, ".konchrc")
    with open(fpath, "w") as fp:
        fp.write(TEST_CONFIG_WITH_SETUP_AND_TEARDOWN)

    def finalize():
        os.remove(fpath)

    request.addfinalizer(finalize)
    return env


@pytest.fixture
def folderenv(request, env):
    folder = os.path.abspath(os.path.join(env.base_path, "testdir"))
    os.makedirs(folder)

    def finalize():
        os.removedirs(folder)

    request.addfinalizer(finalize)
    return env


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_default_config(names_env):
    # Explicitly specify ipython shell because test isn't compatible with ptpython
    res = names_env.run("konch", expect_stderr=True)
    assert_in_output("Default", res)
    assert_in_output("foo", res)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_setup_teardown(setup_env):
    res = setup_env.run("konch", expect_stderr=True)
    assert_in_output("setup!", res)
    assert_in_output("teardown!", res)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_selecting_named_config(names_env):
    res = names_env.run("konch", "-n", "conf2", expect_stderr=True)
    assert_in_output("Conf2", res)
    assert_in_output("bar", res)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_named_config_with_multiple_names(names_env):
    res = names_env.run("konch", "-n", "conf3", expect_stderr=True)
    assert_in_output("Conf3", res)
    assert_in_output("baz", res)

    res = names_env.run("konch", "-n", "c3", expect_stderr=True)
    assert_in_output("Conf3", res)
    assert_in_output("baz", res)


@pytest.mark.skipif(HAS_PTPYTHON, reason="test incompatible with ptpython")
def test_selecting_name_that_doesnt_exist(names_env):
    res = names_env.run("konch", "-n", "doesntexist", expect_stderr=True)
    assert_in_output("Default", res)


def test_resolve_path(folderenv):
    folderenv.run("konch", "init")
    fpath = os.path.abspath(os.path.join(folderenv.base_path, ".konchrc"))
    assert os.path.exists(fpath)
    folder = os.path.abspath(os.path.join(folderenv.base_path, "testdir"))
    os.chdir(folder)
    assert konch.resolve_path(".konchrc") == fpath
