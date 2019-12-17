from cerebralcortex.core.datatypes.datastream import DataStream
from cerebralcortex.core.metadata_manager.stream.metadata import Metadata
from datetime import datetime, timedelta

from cerebralcortex.core.metadata_manager.stream.metadata import Metadata, DataDescriptor, ModuleMetadata
from cerebralcortex.core.util.spark_helper import get_or_create_sc
import re
import sys
from typing import List
import numpy as np
import os
import pathlib
import unittest
import warnings

from cerebralcortex import Kernel
from cerebralcortex.test_suite.test_object_storage import TestObjectStorage
from cerebralcortex.test_suite.test_sql_storage import SqlStorageTest
from cerebralcortex.test_suite.test_stream import DataStreamTest
from functools import reduce
import math
from datetime import timedelta
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.functions import udf
from pyspark.sql.types import *
# from pyspark.sql.functions import pandas_udf,PandasUDFType
from operator import attrgetter
from pyspark.sql.types import StructType
from pyspark.sql.functions import pandas_udf, PandasUDFType
from pyspark.sql.window import Window



def get_orientation_data(ds, sensor_type, wrist, ori=1, is_new_device=False):
    left_ori = {"old": {0: [1, 1, 1], 1: [1, 1, 1], 2: [-1, -1, 1], 3: [-1, 1, 1], 4: [1, -1, 1]},
                "new": {0: [-1, 1, 1], 1: [-1, 1, 1], 2: [1, -1, 1], 3: [1, 1, 1], 4: [-1, -1, 1]}}
    right_ori = {"old": {0: [1, -1, 1], 1: [1, -1, 1], 2: [-1, 1, 1], 3: [-1, -1, 1], 4: [1, 1, 1]},
                 "new": {0: [1, 1, 1], 1: [1, 1, 1], 2: [-1, -1, 1], 3: [-1, 1, 1], 4: [1, -1, 1]}}
    if is_new_device:
        left_fac = left_ori.get("new").get(ori)
        right_fac = right_ori.get("new").get(ori)

    else:
        left_fac = left_ori.get("old").get(ori)
        right_fac = right_ori.get("old").get(ori)

    if wrist == "left":
        fac = left_fac
    elif wrist == "right":
        fac = right_fac
    else:
        raise Exception("wrist can only be left or right.")

    if sensor_type == "gyro":
        data = ds.withColumn("gyroscope_x", ds.gyroscope_x * fac[0]) \
            .withColumn("gyroscope_y", ds.gyroscope_y * fac[1]) \
            .withColumn("gyroscope_z", ds.gyroscope_z * fac[2])
    elif sensor_type == "accel":
        data = ds.withColumn("accelerometer_x", ds.accelerometer_x * fac[0]) \
            .withColumn("accelerometer_y", ds.accelerometer_y * fac[1]) \
            .withColumn("accelerometer_z", ds.accelerometer_z * fac[2])
    else:
        raise Exception("Only gyro or accel sensor_type are allowed.")

    return data


def get_candidates(ds):
    window = Window.partitionBy(["user", "version"]).rowsBetween(-3, 3).orderBy("timestamp")

    @pandas_udf(IntegerType(), PandasUDFType.GROUPED_AGG)
    def generate_candidates(accel_y):
        accel_y[accel_y > 0.1] = 1
        accel_y[accel_y <= 0.1] = 0

        if accel_y.mean() >= 0.5:
            return 1
        else:
            return 0

    return ds.withColumn("candidate", generate_candidates(ds.accelerometer_y).over(window))