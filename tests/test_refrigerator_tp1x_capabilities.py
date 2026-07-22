"""Tests for the TP1X_REF_21K refrigerator dump (issue #21)."""
from custom_components.localthings.registry.adapter import flatten
from custom_components.localthings.registry.by_type import for_device_by_model
from custom_components.localthings.registry.capabilities import common, fridge, ignored
from custom_components.localthings.registry.discovery import discover
from custom_components.localthings.registry.entities import SelectDesc, SensorDesc

from tests.conftest import _load_device


def _fridge():
    resources = _load_device('refrigerator_tp1x')
    info = resources['/information/vs/0']
    reg = for_device_by_model(
        info['x.com.samsung.da.modelNum'], info['x.com.samsung.da.description'],
    )
    return reg, resources


def _state():
    reg, resources = _fridge()
    bound = discover(resources, reg.capabilities, reg.pattern_capabilities)
    return flatten(bound, resources)


def test_model_resolves_to_refrigerator_registry():
    reg, _ = _fridge()
    assert reg is not None and reg.name == 'refrigerator'


def test_no_unbound_hrefs():
    """Every resource in the TP1X dump binds or is ignored -- clears the
    coverage-gap repair."""
    reg, resources = _fridge()
    unbound = []
    discover(resources, reg.capabilities, reg.pattern_capabilities, log=unbound.append)
    assert unbound == []


def test_expected_entities_present():
    state = _state()
    for key in ('ai_energy_level', 'vacation_mode', 'convertible_compartment',
                'selfcheck_error', 'icemaker_one_type', 'icemaker_one_enabled',
                'freezer_temperature', 'cooler_setpoint'):
        assert key in state, key


def test_icemaker_ocf_fallback_declines_when_unit_resource_present():
    """/icemaker/status/0 is bound (not a gap) but produces no entity here --
    /icemaker/one/vs/0 already covers the ice maker, so no duplicate switch."""
    _, resources = _fridge()
    assert '/icemaker/status/0' in resources
    cap = fridge.ICEMAKER_STATUS_OCF_FALLBACK
    assert not cap.match_fn(resources['/icemaker/status/0'], resources)
    assert not fridge.ICEMAKER_STATUS_FALLBACK.match_fn(
        resources['/icemaker/status/vs/0'], resources)


def test_icemaker_ocf_fallback_binds_on_a_status_only_fridge():
    """A simpler model exposing only /icemaker/status/0 still gets a switch."""
    resources = {'/icemaker/status/0': {'status': 'On'}}
    cap = fridge.ICEMAKER_STATUS_OCF_FALLBACK
    bound = discover(resources, {cap.href: [cap]})
    assert flatten(bound, resources) == {'ice_maker_enabled': True}
    desc = cap.entities[0]
    assert desc.write_fn(False, resources['/icemaker/status/0']) == (
        ['icemaker', 'status', '0'], {'status': 'Off'})


def test_mode_flags_and_flex_zone_are_mutually_exclusive():
    """Both capabilities sit on /mode/vs/0; exactly one binds per device."""
    _, tp1x = _fridge()
    rf9000 = _load_device('refrigerator')
    for resources, expect_flex in ((tp1x, False), (rf9000, True)):
        rep = resources['/mode/vs/0']
        assert fridge.FLEX_ZONE.match_fn(rep, resources) is expect_flex
        assert fridge.MODE_FLAGS.match_fn(rep, resources) is not expect_flex


def test_mode_flags_read_only_values():
    state = _state()
    assert state['vacation_mode'] is False        # RVACATION_OFF
    assert state['convertible_compartment'] == 'fconvert_freezer'
    assert all(getattr(d, 'write_fn', None) is None
               for d in fridge.MODE_FLAGS.entities)


def test_mode_flags_gated_off_without_tokens():
    """A fridge whose modes carry neither token gets no phantom entities."""
    resources = {'/mode/vs/0': {'x.com.samsung.da.modes': ['WATERFILTER_ENABLE']}}
    bound = discover(resources, {fridge.MODE_FLAGS.href: [fridge.MODE_FLAGS]})
    assert flatten(bound, resources) == {}


def test_ai_energy_level_select_is_scoped_to_the_fridge_registry():
    """Un-ignored globally so the fridge capability can bind it; only the
    refrigerator registry declares it."""
    assert '/energy/ailevel/vs/0' not in {c.href for c in ignored.IGNORED}
    desc = fridge.AI_ENERGY_LEVEL.entities[0]
    assert desc.options_field == 'supportedAiLevel'
    assert desc.translation_key == 'ai_energy_level'
    assert desc.write_fn('2', {}) == (
        ['energy', 'ailevel', 'vs', '0'], {'aiLevel': '2'})


def test_ai_energy_level_hidden_with_a_single_supported_level():
    desc = fridge.AI_ENERGY_LEVEL.entities[0]
    assert not desc.exists_fn({'aiLevel': '1', 'supportedAiLevel': ['1']}, {})
    assert desc.exists_fn({'aiLevel': '1', 'supportedAiLevel': ['1', '2']}, {})


def test_ice_type_sensor_replaces_select_without_a_supported_list():
    ice_type = [e for e in fridge.ICEMAKER_GENERIC.entities if e.key == 'type']
    select = next(e for e in ice_type if isinstance(e, SelectDesc))
    sensor = next(e for e in ice_type if isinstance(e, SensorDesc))
    toggle = {'x.com.samsung.da.iceType.desired': 'NORMAL'}
    mode = dict(toggle, **{'x.com.samsung.da.iceType.supported': ['NORMAL']})
    assert sensor.exists_fn(toggle, {}) and not select.exists_fn(toggle, {})
    assert select.exists_fn(mode, {}) and not sensor.exists_fn(mode, {})


def test_water_filter_reset_button_writes_the_reported_reset_type():
    desc = next(e for e in common.WATER_FILTER.entities
                if e.key == 'filter_reset')
    rep = {'x.com.samsung.da.filterResetType': ['replaceable']}
    assert desc.exists_fn(rep, {})
    assert not desc.exists_fn({}, {})
    assert desc.write_fn('', rep) == (
        ['filter', 'waterfilter', 'vs', '0'],
        {'x.com.samsung.da.filterResetType': 'replaceable'})
