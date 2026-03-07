import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PassiveInfraredTrait(_message.Message):
    __slots__ = ("passiveInfraredSignalValue", "passiveInfraredBaselineValue", "faultInformation")
    class PassiveInfraredFaultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PASSIVE_INFRARED_FAULT_TYPE_UNSPECIFIED: _ClassVar[PassiveInfraredTrait.PassiveInfraredFaultType]
        PASSIVE_INFRARED_FAULT_TYPE_NONE: _ClassVar[PassiveInfraredTrait.PassiveInfraredFaultType]
        PASSIVE_INFRARED_FAULT_TYPE_UNRESPONSIVE: _ClassVar[PassiveInfraredTrait.PassiveInfraredFaultType]
        PASSIVE_INFRARED_FAULT_TYPE_STUCK: _ClassVar[PassiveInfraredTrait.PassiveInfraredFaultType]
    PASSIVE_INFRARED_FAULT_TYPE_UNSPECIFIED: PassiveInfraredTrait.PassiveInfraredFaultType
    PASSIVE_INFRARED_FAULT_TYPE_NONE: PassiveInfraredTrait.PassiveInfraredFaultType
    PASSIVE_INFRARED_FAULT_TYPE_UNRESPONSIVE: PassiveInfraredTrait.PassiveInfraredFaultType
    PASSIVE_INFRARED_FAULT_TYPE_STUCK: PassiveInfraredTrait.PassiveInfraredFaultType
    class PassiveInfraredSample(_message.Message):
        __slots__ = ("value",)
        VALUE_FIELD_NUMBER: _ClassVar[int]
        value: _wrappers_pb2.FloatValue
        def __init__(self, value: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ...) -> None: ...
    class PassiveInfraredFaultInformation(_message.Message):
        __slots__ = ("asserted", "type", "signalLastValue", "baselineLastValue")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        SIGNALLASTVALUE_FIELD_NUMBER: _ClassVar[int]
        BASELINELASTVALUE_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: PassiveInfraredTrait.PassiveInfraredFaultType
        signalLastValue: PassiveInfraredTrait.PassiveInfraredSample
        baselineLastValue: PassiveInfraredTrait.PassiveInfraredSample
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[PassiveInfraredTrait.PassiveInfraredFaultType, str]] = ..., signalLastValue: _Optional[_Union[PassiveInfraredTrait.PassiveInfraredSample, _Mapping]] = ..., baselineLastValue: _Optional[_Union[PassiveInfraredTrait.PassiveInfraredSample, _Mapping]] = ...) -> None: ...
    class PassiveInfraredSignalPeriodicSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "signalSamples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        SIGNALSAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        signalSamples: _containers.RepeatedCompositeFieldContainer[PassiveInfraredTrait.PassiveInfraredSample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., signalSamples: _Optional[_Iterable[_Union[PassiveInfraredTrait.PassiveInfraredSample, _Mapping]]] = ...) -> None: ...
    class PassiveInfraredBaselinePeriodicSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "baselineSamples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        BASELINESAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        baselineSamples: _containers.RepeatedCompositeFieldContainer[PassiveInfraredTrait.PassiveInfraredSample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., baselineSamples: _Optional[_Iterable[_Union[PassiveInfraredTrait.PassiveInfraredSample, _Mapping]]] = ...) -> None: ...
    class PassiveInfraredDifferentialPeriodicSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "deltaSamples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        DELTASAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        deltaSamples: _containers.RepeatedCompositeFieldContainer[PassiveInfraredTrait.PassiveInfraredSample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., deltaSamples: _Optional[_Iterable[_Union[PassiveInfraredTrait.PassiveInfraredSample, _Mapping]]] = ...) -> None: ...
    class PassiveInfraredFaultEvent(_message.Message):
        __slots__ = ("asserted", "type", "signalLastValue", "baselineLastValue", "durationSinceLastSample", "lastSamplePeriod")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        SIGNALLASTVALUE_FIELD_NUMBER: _ClassVar[int]
        BASELINELASTVALUE_FIELD_NUMBER: _ClassVar[int]
        DURATIONSINCELASTSAMPLE_FIELD_NUMBER: _ClassVar[int]
        LASTSAMPLEPERIOD_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: PassiveInfraredTrait.PassiveInfraredFaultType
        signalLastValue: PassiveInfraredTrait.PassiveInfraredSample
        baselineLastValue: PassiveInfraredTrait.PassiveInfraredSample
        durationSinceLastSample: _duration_pb2.Duration
        lastSamplePeriod: _duration_pb2.Duration
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[PassiveInfraredTrait.PassiveInfraredFaultType, str]] = ..., signalLastValue: _Optional[_Union[PassiveInfraredTrait.PassiveInfraredSample, _Mapping]] = ..., baselineLastValue: _Optional[_Union[PassiveInfraredTrait.PassiveInfraredSample, _Mapping]] = ..., durationSinceLastSample: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., lastSamplePeriod: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    class PassiveInfraredSignalStatisticsEvent(_message.Message):
        __slots__ = ("histogramBoundaries", "histogramCounts", "vacancyExpected")
        HISTOGRAMBOUNDARIES_FIELD_NUMBER: _ClassVar[int]
        HISTOGRAMCOUNTS_FIELD_NUMBER: _ClassVar[int]
        VACANCYEXPECTED_FIELD_NUMBER: _ClassVar[int]
        histogramBoundaries: _containers.RepeatedScalarFieldContainer[int]
        histogramCounts: _containers.RepeatedScalarFieldContainer[int]
        vacancyExpected: bool
        def __init__(self, histogramBoundaries: _Optional[_Iterable[int]] = ..., histogramCounts: _Optional[_Iterable[int]] = ..., vacancyExpected: bool = ...) -> None: ...
    PASSIVEINFRAREDSIGNALVALUE_FIELD_NUMBER: _ClassVar[int]
    PASSIVEINFRAREDBASELINEVALUE_FIELD_NUMBER: _ClassVar[int]
    FAULTINFORMATION_FIELD_NUMBER: _ClassVar[int]
    passiveInfraredSignalValue: PassiveInfraredTrait.PassiveInfraredSample
    passiveInfraredBaselineValue: PassiveInfraredTrait.PassiveInfraredSample
    faultInformation: PassiveInfraredTrait.PassiveInfraredFaultInformation
    def __init__(self, passiveInfraredSignalValue: _Optional[_Union[PassiveInfraredTrait.PassiveInfraredSample, _Mapping]] = ..., passiveInfraredBaselineValue: _Optional[_Union[PassiveInfraredTrait.PassiveInfraredSample, _Mapping]] = ..., faultInformation: _Optional[_Union[PassiveInfraredTrait.PassiveInfraredFaultInformation, _Mapping]] = ...) -> None: ...

class SmokeTrait(_message.Message):
    __slots__ = ("infraredLedValue", "blueLedValue", "infraredLedFault", "blueLedFault")
    class SmokeFaultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SMOKE_FAULT_TYPE_UNSPECIFIED: _ClassVar[SmokeTrait.SmokeFaultType]
        SMOKE_FAULT_TYPE_NONE: _ClassVar[SmokeTrait.SmokeFaultType]
        SMOKE_FAULT_TYPE_UNRESPONSIVE: _ClassVar[SmokeTrait.SmokeFaultType]
    SMOKE_FAULT_TYPE_UNSPECIFIED: SmokeTrait.SmokeFaultType
    SMOKE_FAULT_TYPE_NONE: SmokeTrait.SmokeFaultType
    SMOKE_FAULT_TYPE_UNRESPONSIVE: SmokeTrait.SmokeFaultType
    class SmokeSample(_message.Message):
        __slots__ = ("sample",)
        SAMPLE_FIELD_NUMBER: _ClassVar[int]
        sample: _wrappers_pb2.FloatValue
        def __init__(self, sample: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ...) -> None: ...
    class SmokeFaultInformation(_message.Message):
        __slots__ = ("asserted", "type", "lastValue")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: SmokeTrait.SmokeFaultType
        lastValue: SmokeTrait.SmokeSample
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[SmokeTrait.SmokeFaultType, str]] = ..., lastValue: _Optional[_Union[SmokeTrait.SmokeSample, _Mapping]] = ...) -> None: ...
    class InfraredLedFaultEvent(_message.Message):
        __slots__ = ("asserted", "type", "lastValue", "durationSinceLastSample", "lastSamplePeriod")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        DURATIONSINCELASTSAMPLE_FIELD_NUMBER: _ClassVar[int]
        LASTSAMPLEPERIOD_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: SmokeTrait.SmokeFaultType
        lastValue: SmokeTrait.SmokeSample
        durationSinceLastSample: _duration_pb2.Duration
        lastSamplePeriod: _duration_pb2.Duration
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[SmokeTrait.SmokeFaultType, str]] = ..., lastValue: _Optional[_Union[SmokeTrait.SmokeSample, _Mapping]] = ..., durationSinceLastSample: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., lastSamplePeriod: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    class BlueLedFaultEvent(_message.Message):
        __slots__ = ("asserted", "type", "lastValue", "durationSinceLastSample", "lastSamplePeriod")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        DURATIONSINCELASTSAMPLE_FIELD_NUMBER: _ClassVar[int]
        LASTSAMPLEPERIOD_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: SmokeTrait.SmokeFaultType
        lastValue: SmokeTrait.SmokeSample
        durationSinceLastSample: _duration_pb2.Duration
        lastSamplePeriod: _duration_pb2.Duration
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[SmokeTrait.SmokeFaultType, str]] = ..., lastValue: _Optional[_Union[SmokeTrait.SmokeSample, _Mapping]] = ..., durationSinceLastSample: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., lastSamplePeriod: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    class InfraredLedPeriodicSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "samples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        SAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        samples: _containers.RepeatedCompositeFieldContainer[SmokeTrait.SmokeSample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., samples: _Optional[_Iterable[_Union[SmokeTrait.SmokeSample, _Mapping]]] = ...) -> None: ...
    class BlueLedPeriodicSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "samples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        SAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        samples: _containers.RepeatedCompositeFieldContainer[SmokeTrait.SmokeSample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., samples: _Optional[_Iterable[_Union[SmokeTrait.SmokeSample, _Mapping]]] = ...) -> None: ...
    class ClearAirOffsetSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "irLedSamples", "blueLedSamples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        IRLEDSAMPLES_FIELD_NUMBER: _ClassVar[int]
        BLUELEDSAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        irLedSamples: _containers.RepeatedCompositeFieldContainer[SmokeTrait.SmokeSample]
        blueLedSamples: _containers.RepeatedCompositeFieldContainer[SmokeTrait.SmokeSample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., irLedSamples: _Optional[_Iterable[_Union[SmokeTrait.SmokeSample, _Mapping]]] = ..., blueLedSamples: _Optional[_Iterable[_Union[SmokeTrait.SmokeSample, _Mapping]]] = ...) -> None: ...
    INFRAREDLEDVALUE_FIELD_NUMBER: _ClassVar[int]
    BLUELEDVALUE_FIELD_NUMBER: _ClassVar[int]
    INFRAREDLEDFAULT_FIELD_NUMBER: _ClassVar[int]
    BLUELEDFAULT_FIELD_NUMBER: _ClassVar[int]
    infraredLedValue: SmokeTrait.SmokeSample
    blueLedValue: SmokeTrait.SmokeSample
    infraredLedFault: SmokeTrait.SmokeFaultInformation
    blueLedFault: SmokeTrait.SmokeFaultInformation
    def __init__(self, infraredLedValue: _Optional[_Union[SmokeTrait.SmokeSample, _Mapping]] = ..., blueLedValue: _Optional[_Union[SmokeTrait.SmokeSample, _Mapping]] = ..., infraredLedFault: _Optional[_Union[SmokeTrait.SmokeFaultInformation, _Mapping]] = ..., blueLedFault: _Optional[_Union[SmokeTrait.SmokeFaultInformation, _Mapping]] = ...) -> None: ...

class TemperatureTrait(_message.Message):
    __slots__ = ("temperatureValue", "faultInformation")
    class TemperatureFaultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TEMPERATURE_FAULT_TYPE_UNSPECIFIED: _ClassVar[TemperatureTrait.TemperatureFaultType]
        TEMPERATURE_FAULT_TYPE_NONE: _ClassVar[TemperatureTrait.TemperatureFaultType]
        TEMPERATURE_FAULT_TYPE_UNRESPONSIVE: _ClassVar[TemperatureTrait.TemperatureFaultType]
        TEMPERATURE_FAULT_TYPE_OUT_OF_NORMAL_RANGE: _ClassVar[TemperatureTrait.TemperatureFaultType]
    TEMPERATURE_FAULT_TYPE_UNSPECIFIED: TemperatureTrait.TemperatureFaultType
    TEMPERATURE_FAULT_TYPE_NONE: TemperatureTrait.TemperatureFaultType
    TEMPERATURE_FAULT_TYPE_UNRESPONSIVE: TemperatureTrait.TemperatureFaultType
    TEMPERATURE_FAULT_TYPE_OUT_OF_NORMAL_RANGE: TemperatureTrait.TemperatureFaultType
    class TemperatureSample(_message.Message):
        __slots__ = ("temperature",)
        TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
        temperature: _wrappers_pb2.FloatValue
        def __init__(self, temperature: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ...) -> None: ...
    class TemperatureFaultInformation(_message.Message):
        __slots__ = ("asserted", "type", "lastValue")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: TemperatureTrait.TemperatureFaultType
        lastValue: TemperatureTrait.TemperatureSample
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[TemperatureTrait.TemperatureFaultType, str]] = ..., lastValue: _Optional[_Union[TemperatureTrait.TemperatureSample, _Mapping]] = ...) -> None: ...
    class TemperatureSensorFaultEvent(_message.Message):
        __slots__ = ("asserted", "type", "lastValue", "durationSinceLastSample", "lastSamplePeriod")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        DURATIONSINCELASTSAMPLE_FIELD_NUMBER: _ClassVar[int]
        LASTSAMPLEPERIOD_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: TemperatureTrait.TemperatureFaultType
        lastValue: TemperatureTrait.TemperatureSample
        durationSinceLastSample: _duration_pb2.Duration
        lastSamplePeriod: _duration_pb2.Duration
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[TemperatureTrait.TemperatureFaultType, str]] = ..., lastValue: _Optional[_Union[TemperatureTrait.TemperatureSample, _Mapping]] = ..., durationSinceLastSample: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., lastSamplePeriod: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    class TemperaturePeriodicSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "samples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        SAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        samples: _containers.RepeatedCompositeFieldContainer[TemperatureTrait.TemperatureSample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., samples: _Optional[_Iterable[_Union[TemperatureTrait.TemperatureSample, _Mapping]]] = ...) -> None: ...
    TEMPERATUREVALUE_FIELD_NUMBER: _ClassVar[int]
    FAULTINFORMATION_FIELD_NUMBER: _ClassVar[int]
    temperatureValue: TemperatureTrait.TemperatureSample
    faultInformation: TemperatureTrait.TemperatureFaultInformation
    def __init__(self, temperatureValue: _Optional[_Union[TemperatureTrait.TemperatureSample, _Mapping]] = ..., faultInformation: _Optional[_Union[TemperatureTrait.TemperatureFaultInformation, _Mapping]] = ...) -> None: ...

class CarbonMonoxideTrait(_message.Message):
    __slots__ = ("value", "faultInformation")
    class CoFaultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        CO_FAULT_TYPE_UNSPECIFIED: _ClassVar[CarbonMonoxideTrait.CoFaultType]
        CO_FAULT_TYPE_NONE: _ClassVar[CarbonMonoxideTrait.CoFaultType]
        CO_FAULT_TYPE_UNRESPONSIVE: _ClassVar[CarbonMonoxideTrait.CoFaultType]
        CO_FAULT_TYPE_END_OF_LIFE: _ClassVar[CarbonMonoxideTrait.CoFaultType]
    CO_FAULT_TYPE_UNSPECIFIED: CarbonMonoxideTrait.CoFaultType
    CO_FAULT_TYPE_NONE: CarbonMonoxideTrait.CoFaultType
    CO_FAULT_TYPE_UNRESPONSIVE: CarbonMonoxideTrait.CoFaultType
    CO_FAULT_TYPE_END_OF_LIFE: CarbonMonoxideTrait.CoFaultType
    class CoSample(_message.Message):
        __slots__ = ("ppm",)
        PPM_FIELD_NUMBER: _ClassVar[int]
        ppm: int
        def __init__(self, ppm: _Optional[int] = ...) -> None: ...
    class CoFaultInformation(_message.Message):
        __slots__ = ("asserted", "type", "lastValue")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: CarbonMonoxideTrait.CoFaultType
        lastValue: CarbonMonoxideTrait.CoSample
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[CarbonMonoxideTrait.CoFaultType, str]] = ..., lastValue: _Optional[_Union[CarbonMonoxideTrait.CoSample, _Mapping]] = ...) -> None: ...
    class CoFaultEvent(_message.Message):
        __slots__ = ("asserted", "type", "lastValue", "durationSinceLastSample", "lastSamplePeriod")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        DURATIONSINCELASTSAMPLE_FIELD_NUMBER: _ClassVar[int]
        LASTSAMPLEPERIOD_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: CarbonMonoxideTrait.CoFaultType
        lastValue: CarbonMonoxideTrait.CoSample
        durationSinceLastSample: _duration_pb2.Duration
        lastSamplePeriod: _duration_pb2.Duration
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[CarbonMonoxideTrait.CoFaultType, str]] = ..., lastValue: _Optional[_Union[CarbonMonoxideTrait.CoSample, _Mapping]] = ..., durationSinceLastSample: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., lastSamplePeriod: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    class CoPeriodicSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "samples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        SAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        samples: _containers.RepeatedCompositeFieldContainer[CarbonMonoxideTrait.CoSample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., samples: _Optional[_Iterable[_Union[CarbonMonoxideTrait.CoSample, _Mapping]]] = ...) -> None: ...
    VALUE_FIELD_NUMBER: _ClassVar[int]
    FAULTINFORMATION_FIELD_NUMBER: _ClassVar[int]
    value: CarbonMonoxideTrait.CoSample
    faultInformation: CarbonMonoxideTrait.CoFaultInformation
    def __init__(self, value: _Optional[_Union[CarbonMonoxideTrait.CoSample, _Mapping]] = ..., faultInformation: _Optional[_Union[CarbonMonoxideTrait.CoFaultInformation, _Mapping]] = ...) -> None: ...

class BatteryVoltageTrait(_message.Message):
    __slots__ = ("batteryValue", "faultInformation")
    class BatteryVoltageFaultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BATTERY_VOLTAGE_FAULT_TYPE_UNSPECIFIED: _ClassVar[BatteryVoltageTrait.BatteryVoltageFaultType]
        BATTERY_VOLTAGE_FAULT_TYPE_NONE: _ClassVar[BatteryVoltageTrait.BatteryVoltageFaultType]
        BATTERY_VOLTAGE_FAULT_TYPE_OUT_OF_OPERATING_RANGE: _ClassVar[BatteryVoltageTrait.BatteryVoltageFaultType]
        BATTERY_VOLTAGE_FAULT_TYPE_UNRESPONSIVE: _ClassVar[BatteryVoltageTrait.BatteryVoltageFaultType]
        BATTERY_VOLTAGE_FAULT_TYPE_DISCONNECTED: _ClassVar[BatteryVoltageTrait.BatteryVoltageFaultType]
        BATTERY_VOLTAGE_FAULT_TYPE_END_OF_LIFE: _ClassVar[BatteryVoltageTrait.BatteryVoltageFaultType]
    BATTERY_VOLTAGE_FAULT_TYPE_UNSPECIFIED: BatteryVoltageTrait.BatteryVoltageFaultType
    BATTERY_VOLTAGE_FAULT_TYPE_NONE: BatteryVoltageTrait.BatteryVoltageFaultType
    BATTERY_VOLTAGE_FAULT_TYPE_OUT_OF_OPERATING_RANGE: BatteryVoltageTrait.BatteryVoltageFaultType
    BATTERY_VOLTAGE_FAULT_TYPE_UNRESPONSIVE: BatteryVoltageTrait.BatteryVoltageFaultType
    BATTERY_VOLTAGE_FAULT_TYPE_DISCONNECTED: BatteryVoltageTrait.BatteryVoltageFaultType
    BATTERY_VOLTAGE_FAULT_TYPE_END_OF_LIFE: BatteryVoltageTrait.BatteryVoltageFaultType
    class BatteryVoltageSample(_message.Message):
        __slots__ = ("batteryVoltage",)
        BATTERYVOLTAGE_FIELD_NUMBER: _ClassVar[int]
        batteryVoltage: _wrappers_pb2.FloatValue
        def __init__(self, batteryVoltage: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ...) -> None: ...
    class BatteryVoltageFaultInformation(_message.Message):
        __slots__ = ("asserted", "type", "lastValue")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: BatteryVoltageTrait.BatteryVoltageFaultType
        lastValue: BatteryVoltageTrait.BatteryVoltageSample
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[BatteryVoltageTrait.BatteryVoltageFaultType, str]] = ..., lastValue: _Optional[_Union[BatteryVoltageTrait.BatteryVoltageSample, _Mapping]] = ...) -> None: ...
    class BatteryVoltageFaultEvent(_message.Message):
        __slots__ = ("asserted", "type", "lastValue", "durationSinceLastSample")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        DURATIONSINCELASTSAMPLE_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: BatteryVoltageTrait.BatteryVoltageFaultType
        lastValue: BatteryVoltageTrait.BatteryVoltageSample
        durationSinceLastSample: _duration_pb2.Duration
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[BatteryVoltageTrait.BatteryVoltageFaultType, str]] = ..., lastValue: _Optional[_Union[BatteryVoltageTrait.BatteryVoltageSample, _Mapping]] = ..., durationSinceLastSample: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    class BatteryVoltagePeriodicSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "samples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        SAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        samples: _containers.RepeatedCompositeFieldContainer[BatteryVoltageTrait.BatteryVoltageSample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., samples: _Optional[_Iterable[_Union[BatteryVoltageTrait.BatteryVoltageSample, _Mapping]]] = ...) -> None: ...
    class BatteryVoltageStatisticsEvent(_message.Message):
        __slots__ = ("meanVoltage", "minimumVoltage", "maximumVoltage", "numSamples", "statsSampleInterval")
        MEANVOLTAGE_FIELD_NUMBER: _ClassVar[int]
        MINIMUMVOLTAGE_FIELD_NUMBER: _ClassVar[int]
        MAXIMUMVOLTAGE_FIELD_NUMBER: _ClassVar[int]
        NUMSAMPLES_FIELD_NUMBER: _ClassVar[int]
        STATSSAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        meanVoltage: BatteryVoltageTrait.BatteryVoltageSample
        minimumVoltage: BatteryVoltageTrait.BatteryVoltageSample
        maximumVoltage: BatteryVoltageTrait.BatteryVoltageSample
        numSamples: int
        statsSampleInterval: _duration_pb2.Duration
        def __init__(self, meanVoltage: _Optional[_Union[BatteryVoltageTrait.BatteryVoltageSample, _Mapping]] = ..., minimumVoltage: _Optional[_Union[BatteryVoltageTrait.BatteryVoltageSample, _Mapping]] = ..., maximumVoltage: _Optional[_Union[BatteryVoltageTrait.BatteryVoltageSample, _Mapping]] = ..., numSamples: _Optional[int] = ..., statsSampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    BATTERYVALUE_FIELD_NUMBER: _ClassVar[int]
    FAULTINFORMATION_FIELD_NUMBER: _ClassVar[int]
    batteryValue: BatteryVoltageTrait.BatteryVoltageSample
    faultInformation: BatteryVoltageTrait.BatteryVoltageFaultInformation
    def __init__(self, batteryValue: _Optional[_Union[BatteryVoltageTrait.BatteryVoltageSample, _Mapping]] = ..., faultInformation: _Optional[_Union[BatteryVoltageTrait.BatteryVoltageFaultInformation, _Mapping]] = ...) -> None: ...

class AmbientLightTrait(_message.Message):
    __slots__ = ("ambientLightValue", "faultInformation")
    class AmbientLightFaultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        AMBIENT_LIGHT_FAULT_TYPE_UNSPECIFIED: _ClassVar[AmbientLightTrait.AmbientLightFaultType]
        AMBIENT_LIGHT_FAULT_TYPE_NONE: _ClassVar[AmbientLightTrait.AmbientLightFaultType]
        AMBIENT_LIGHT_FAULT_TYPE_UNRESPONSIVE: _ClassVar[AmbientLightTrait.AmbientLightFaultType]
    AMBIENT_LIGHT_FAULT_TYPE_UNSPECIFIED: AmbientLightTrait.AmbientLightFaultType
    AMBIENT_LIGHT_FAULT_TYPE_NONE: AmbientLightTrait.AmbientLightFaultType
    AMBIENT_LIGHT_FAULT_TYPE_UNRESPONSIVE: AmbientLightTrait.AmbientLightFaultType
    class AmbientLightSample(_message.Message):
        __slots__ = ("ambientLight",)
        AMBIENTLIGHT_FIELD_NUMBER: _ClassVar[int]
        ambientLight: _wrappers_pb2.FloatValue
        def __init__(self, ambientLight: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ...) -> None: ...
    class AmbientLightFaultInformation(_message.Message):
        __slots__ = ("asserted", "type", "lastValue")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: AmbientLightTrait.AmbientLightFaultType
        lastValue: AmbientLightTrait.AmbientLightSample
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[AmbientLightTrait.AmbientLightFaultType, str]] = ..., lastValue: _Optional[_Union[AmbientLightTrait.AmbientLightSample, _Mapping]] = ...) -> None: ...
    class AmbientLightFaultEvent(_message.Message):
        __slots__ = ("asserted", "type", "lastValue", "durationSinceLastSample", "lastSamplePeriod")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        DURATIONSINCELASTSAMPLE_FIELD_NUMBER: _ClassVar[int]
        LASTSAMPLEPERIOD_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: AmbientLightTrait.AmbientLightFaultType
        lastValue: AmbientLightTrait.AmbientLightSample
        durationSinceLastSample: _duration_pb2.Duration
        lastSamplePeriod: _duration_pb2.Duration
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[AmbientLightTrait.AmbientLightFaultType, str]] = ..., lastValue: _Optional[_Union[AmbientLightTrait.AmbientLightSample, _Mapping]] = ..., durationSinceLastSample: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., lastSamplePeriod: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    class AmbientLightPeriodicSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "samples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        SAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        samples: _containers.RepeatedCompositeFieldContainer[AmbientLightTrait.AmbientLightSample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., samples: _Optional[_Iterable[_Union[AmbientLightTrait.AmbientLightSample, _Mapping]]] = ...) -> None: ...
    AMBIENTLIGHTVALUE_FIELD_NUMBER: _ClassVar[int]
    FAULTINFORMATION_FIELD_NUMBER: _ClassVar[int]
    ambientLightValue: AmbientLightTrait.AmbientLightSample
    faultInformation: AmbientLightTrait.AmbientLightFaultInformation
    def __init__(self, ambientLightValue: _Optional[_Union[AmbientLightTrait.AmbientLightSample, _Mapping]] = ..., faultInformation: _Optional[_Union[AmbientLightTrait.AmbientLightFaultInformation, _Mapping]] = ...) -> None: ...

class HumidityTrait(_message.Message):
    __slots__ = ("humidityValue", "faultInformation")
    class HumidityFaultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HUMIDITY_FAULT_TYPE_UNSPECIFIED: _ClassVar[HumidityTrait.HumidityFaultType]
        HUMIDITY_FAULT_TYPE_NONE: _ClassVar[HumidityTrait.HumidityFaultType]
        HUMIDITY_FAULT_TYPE_UNRESPONSIVE: _ClassVar[HumidityTrait.HumidityFaultType]
    HUMIDITY_FAULT_TYPE_UNSPECIFIED: HumidityTrait.HumidityFaultType
    HUMIDITY_FAULT_TYPE_NONE: HumidityTrait.HumidityFaultType
    HUMIDITY_FAULT_TYPE_UNRESPONSIVE: HumidityTrait.HumidityFaultType
    class HumiditySample(_message.Message):
        __slots__ = ("humidity",)
        HUMIDITY_FIELD_NUMBER: _ClassVar[int]
        humidity: _wrappers_pb2.FloatValue
        def __init__(self, humidity: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ...) -> None: ...
    class HumidityFaultInformation(_message.Message):
        __slots__ = ("asserted", "type", "lastValue")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: HumidityTrait.HumidityFaultType
        lastValue: HumidityTrait.HumiditySample
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[HumidityTrait.HumidityFaultType, str]] = ..., lastValue: _Optional[_Union[HumidityTrait.HumiditySample, _Mapping]] = ...) -> None: ...
    class HumidityFaultEvent(_message.Message):
        __slots__ = ("asserted", "type", "lastValue", "durationSinceLastSample", "lastSamplePeriod")
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        LASTVALUE_FIELD_NUMBER: _ClassVar[int]
        DURATIONSINCELASTSAMPLE_FIELD_NUMBER: _ClassVar[int]
        LASTSAMPLEPERIOD_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        type: HumidityTrait.HumidityFaultType
        lastValue: HumidityTrait.HumiditySample
        durationSinceLastSample: _duration_pb2.Duration
        lastSamplePeriod: _duration_pb2.Duration
        def __init__(self, asserted: bool = ..., type: _Optional[_Union[HumidityTrait.HumidityFaultType, str]] = ..., lastValue: _Optional[_Union[HumidityTrait.HumiditySample, _Mapping]] = ..., durationSinceLastSample: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., lastSamplePeriod: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    class HumidityPeriodicSamplesEvent(_message.Message):
        __slots__ = ("sampleInterval", "samples")
        SAMPLEINTERVAL_FIELD_NUMBER: _ClassVar[int]
        SAMPLES_FIELD_NUMBER: _ClassVar[int]
        sampleInterval: _duration_pb2.Duration
        samples: _containers.RepeatedCompositeFieldContainer[HumidityTrait.HumiditySample]
        def __init__(self, sampleInterval: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., samples: _Optional[_Iterable[_Union[HumidityTrait.HumiditySample, _Mapping]]] = ...) -> None: ...
    HUMIDITYVALUE_FIELD_NUMBER: _ClassVar[int]
    FAULTINFORMATION_FIELD_NUMBER: _ClassVar[int]
    humidityValue: HumidityTrait.HumiditySample
    faultInformation: HumidityTrait.HumidityFaultInformation
    def __init__(self, humidityValue: _Optional[_Union[HumidityTrait.HumiditySample, _Mapping]] = ..., faultInformation: _Optional[_Union[HumidityTrait.HumidityFaultInformation, _Mapping]] = ...) -> None: ...
