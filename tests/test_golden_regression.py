import json
import types
from pathlib import Path

import pytest

GOLDEN = Path(__file__).parent / 'fixtures' / 'golden'


def _registry_for(resources):
    from custom_components.localthings.registry.by_type import for_device, for_device_by_model
    otn = resources.get('/otninformation/vs/0', {})
    one_ui = otn.get('swVersionInfo', {}).get('oneUiVersion', '')
    info = resources.get('/information/vs/0', {})
    reg = for_device(one_ui) if one_ui else None
    if reg is None:
        reg = for_device_by_model(
            info.get('x.com.samsung.da.modelNum', ''),
            info.get('x.com.samsung.da.description', ''),
        )
    return reg


def _discover(resources):
    from custom_components.localthings.registry.discovery import discover
    reg = _registry_for(resources)
    if reg is None:
        from custom_components.localthings.registry.registry import CAPABILITIES
        caps, pats = CAPABILITIES, []
    else:
        caps, pats = reg.capabilities, reg.pattern_capabilities
    return reg, discover(resources, caps, pats)


def _new_state_keys(name, resources):
    from custom_components.localthings.registry.adapter import flatten
    _, bound = _discover(resources)
    return sorted(flatten(bound, resources).keys())


def _new_discovery_unique_ids(resources):
    """The entities that would actually be registered in HA, as
    'samsung_<device_type>_<state_key>'.

    Broader than state_keys: it runs the real entity.py inclusion gate, so it
    also covers command-only entities (buttons) that flatten() has no value
    for. Regenerate a golden's discovery_unique_ids with this, never by hand.
    """
    from custom_components.localthings.registry.adapter import _key
    from custom_components.localthings.entity import _is_included
    reg, bound = _discover(resources)
    coordinator = types.SimpleNamespace(last_resources=resources)
    name = reg.name if reg else 'unknown'
    return sorted({f'samsung_{name}_{_key(b)}'
                   for b in bound if _is_included(b, coordinator)})


@pytest.mark.parametrize('name,ip', [
    ('dishwasher', '10.0.0.129'),
    ('refrigerator', '10.0.0.254'),
])
def test_registry_reproduces_golden_state_keys(name, ip, request):
    from tests.conftest import _load_resources
    resources = _load_resources(ip)
    golden = json.loads((GOLDEN / f'{name}.json').read_text())
    state_keys = _new_state_keys(name, resources)
    assert set(state_keys) == set(golden['state_keys']), (
        f"state_keys mismatch:\n"
        f"  extra:   {sorted(set(state_keys) - set(golden['state_keys']))}\n"
        f"  missing: {sorted(set(golden['state_keys']) - set(state_keys))}"
    )


def test_registry_reproduces_golden_state_keys_for_washer():
    from tests.conftest import _load_device
    resources = _load_device('washer')
    golden = json.loads((GOLDEN / 'washer.json').read_text())
    state_keys = _new_state_keys('washer', resources)
    assert set(state_keys) == set(golden['state_keys']), (
        f"state_keys mismatch:\n"
        f"  extra:   {sorted(set(state_keys) - set(golden['state_keys']))}\n"
        f"  missing: {sorted(set(golden['state_keys']) - set(state_keys))}"
    )


def test_registry_reproduces_golden_state_keys_for_dryer():
    from tests.conftest import _load_device
    resources = _load_device('dryer')
    golden = json.loads((GOLDEN / 'dryer.json').read_text())
    state_keys = _new_state_keys('dryer', resources)
    assert set(state_keys) == set(golden['state_keys']), (
        f"state_keys mismatch:\n"
        f"  extra:   {sorted(set(state_keys) - set(golden['state_keys']))}\n"
        f"  missing: {sorted(set(golden['state_keys']) - set(state_keys))}"
    )


def test_registry_reproduces_golden_state_keys_for_refrigerator_tp1x():
    from tests.conftest import _load_device
    resources = _load_device('refrigerator_tp1x')
    golden = json.loads((GOLDEN / 'refrigerator_tp1x.json').read_text())
    state_keys = _new_state_keys('refrigerator_tp1x', resources)
    assert set(state_keys) == set(golden['state_keys']), (
        f"state_keys mismatch:\n"
        f"  extra:   {sorted(set(state_keys) - set(golden['state_keys']))}\n"
        f"  missing: {sorted(set(golden['state_keys']) - set(state_keys))}"
    )


def test_registry_reproduces_golden_state_keys_for_airconditioner():
    from tests.conftest import _load_device
    resources = _load_device('airconditioner')
    golden = json.loads((GOLDEN / 'airconditioner.json').read_text())
    state_keys = _new_state_keys('airconditioner', resources)
    assert set(state_keys) == set(golden['state_keys']), (
        f"state_keys mismatch:\n"
        f"  extra:   {sorted(set(state_keys) - set(golden['state_keys']))}\n"
        f"  missing: {sorted(set(golden['state_keys']) - set(state_keys))}"
    )


# Goldens that also pin the registered-entity set, not just the value-bearing
# state keys. Listed explicitly so a regeneration that drops the field fails
# here instead of silently shrinking coverage.
@pytest.mark.parametrize('name', ['dishwasher', 'refrigerator', 'refrigerator_tp1x'])
def test_registry_reproduces_golden_discovery_unique_ids(name):
    from tests.conftest import _load_device
    resources = _load_device(name)
    golden = json.loads((GOLDEN / f'{name}.json').read_text())
    assert 'discovery_unique_ids' in golden, (
        f"{name}.json lost its discovery_unique_ids -- regenerate it with "
        f"_new_discovery_unique_ids(), don't drop the field"
    )
    unique_ids = _new_discovery_unique_ids(resources)
    assert set(unique_ids) == set(golden['discovery_unique_ids']), (
        f"discovery_unique_ids mismatch:\n"
        f"  extra:   {sorted(set(unique_ids) - set(golden['discovery_unique_ids']))}\n"
        f"  missing: {sorted(set(golden['discovery_unique_ids']) - set(unique_ids))}"
    )


def test_resources_from_batch_preferred_over_flat():
    from tests.conftest import _resources_from_dump
    dump = {
        'device0': [
            {'di': 'device'},  # [0] device-level rep, skipped
            {'href': '/foo', 'rep': {'x': 1}},
        ],
        'resources': {'/foo': {'x': 99}},
    }
    result = _resources_from_dump(dump)
    assert result == {'/foo': {'x': 1}}
