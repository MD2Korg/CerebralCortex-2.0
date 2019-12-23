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
import numpy as np
import math
from scipy.stats import skew
from scipy.stats import kurtosis

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

from cerebralcortex.core.datatypes.datastream import DataStream
from cerebralcortex.core.metadata_manager.stream.metadata import Metadata
from cerebralcortex.algorithms.brushing.helper import get_orientation_data, get_candidates, classify_brushing
from cerebralcortex.core.plotting.basic_plots import BasicPlots
from cerebralcortex.core.plotting.stress_plots import StressStreamPlots

#df3=reduce(lambda x, y: x.join(y, ['timestamp'], how='left'), dfs)

sqlContext = get_or_create_sc("sqlContext")
dfa=sqlContext.read.parquet("/home/ali/IdeaProjects/MD2K_DATA/cc3/moral_sample_data/accel/")
dfg=sqlContext.read.parquet("/home/ali/IdeaProjects/MD2K_DATA/cc3/moral_sample_data/gyro/")
dfa = dfa.withColumn("localtime", dfa.timestamp)
dfg = dfg.withColumn("localtime", dfg.timestamp)

##########################################################################################################

CC = Kernel("../../conf/", auto_offset_reset="smallest", study_name="default")

ds_accel = DataStream(data=dfa, metadata=Metadata())
ds_gyro = DataStream(data=dfg, metadata=Metadata())

# interpolation
ds_accel_interpolated = ds_accel.interpolate()
ds_gyro_interpolated = ds_gyro.interpolate()

##compute magnitude
ds_accel_magnitude = ds_accel_interpolated.compute_magnitude(col_names=["accelerometer_x", "accelerometer_y", "accelerometer_z"], magnitude_col_name="accel_magnitude")
ds_gyro_magnitude = ds_gyro_interpolated.compute_magnitude(col_names=["gyroscope_x", "gyroscope_y", "gyroscope_z"], magnitude_col_name="gyro_magnitude")

# join accel and gyro streams
ds_ag = ds_accel_magnitude.join(ds_gyro_magnitude, on=['user', 'timestamp', 'localtime', 'version'], how='full').dropna()

# get orientation
ds_ag_orientation = get_orientation_data(ds_ag,wrist="left")

## apply complementary filter
ds_ag_complemtary_filtered = ds_ag_orientation.complementary_filter()

# get brushing candidate groups
ds_ag_candidates = get_candidates(ds_ag_complemtary_filtered)

#remove where group==0 - non-candidates
ds_ag_candidates=ds_ag_candidates.filter(ds_ag_candidates.candidate==1)


## compute features
ds_fouriar_features=ds_ag_candidates.compute_fouriar_features(exclude_col_names=['group', 'candidate'], groupByColumnName=["group"])
ds_statistical_features = ds_ag_candidates.compute_statistical_features(exclude_col_names=['group','candidate'], groupByColumnName=["group"])
ds_corr_mse_features = ds_ag_candidates.compute_corr_mse_accel_gyro(exclude_col_names=['group','candidate'], groupByColumnName=["group"])

ds_features = ds_fouriar_features\
    .join(ds_statistical_features, on=['user', 'timestamp', 'localtime', 'version'], how='full')\
    .join(ds_corr_mse_features, on=['user', 'timestamp', 'localtime', 'version'], how='full')

pdf_features = ds_features.toPandas()

pdf_predictions = classify_brushing(pdf_features,model_file_name="model/AB_model_brushing_all_features.model")

print(pdf_predictions)



# schema = StructType([
#     StructField("timestamp", TimestampType()),
#     StructField("localtime", TimestampType()),
#     StructField("user", StringType()),
#     StructField("version", IntegerType()),
#     StructField("name", StringType()),
#     StructField("trigger_type", StringType()),
#     StructField("start_time", TimestampType()),
#     StructField("end_time", TimestampType()),
#     StructField("total_time", FloatType()),
#     StructField("total_questions", IntegerType()),
#     StructField("total_answers", FloatType()),
#     StructField("average_question_length", FloatType()),
#     StructField("average_total_answer_options", FloatType()),
#     StructField("time_between_ema", FloatType()),
#     StructField("status", StringType()),
#     StructField("name", StringType()),
#     StructField("trigger_type", StringType()),
#     StructField("start_time", TimestampType()),
#     StructField("end_time", TimestampType()),
#     StructField("total_time", FloatType()),
#     StructField("total_questions", IntegerType()),
#     StructField("total_answers", FloatType()),
#     StructField("average_question_length", FloatType()),
#     StructField("average_total_answer_options", FloatType()),
#     StructField("time_between_ema", FloatType()),
#     StructField("status", StringType()),
#     StructField("question_answers", StringType())
#
#
# ])

def zero_cross_rate(series):
    """
    How often the signal changes sign (+/-)
    """
    series_mean = np.mean(series)
    series = [v-series_mean for v in series]
    zero_cross_count = (np.diff(np.sign(series)) != 0).sum()
    # print('zero_cross_count', zero_cross_count)
    return zero_cross_count / len(series)

def compute_statistical_features(data):
    mean = np.mean(data)
    median = np.median(data)
    std = np.std(data)
    skewness = skew(data)
    kurt = kurtosis(data)
    power = np.mean([v * v for v in data])
    zc = zero_cross_rate(data)
    return [mean, median, std, skewness, kurt, power, zc]

stats_schema = StructType([
    StructField("timestamp", TimestampType()),
    StructField("localtime", TimestampType()),
    StructField("user", StringType()),
    StructField("version", IntegerType()),
])

stats_features = ['mean', 'mode', 'median', 'std', 'variance', 'max', 'min', 'lower_quartile', 'upper_quartile', 'sqrt', 'skewness', 'kurt', 'power', 'zero_crossing']
column_names = ['accelerometer_x', 'accelerometer_y', 'accelerometer_z', 'gyroscope_y', 'gyroscope_x', 'gyroscope_z']
# compute features
# @pandas_udf(schema, PandasUDFType.GROUPED_MAP)
# def interpolate_data(pdf):
#     pdf.set_index("timestamp", inplace=True)
#     pdf = pdf.resample(str(sample_freq)+"ms").bfill(limit=1).interpolate(method=method, axis=axis, limit=limit,inplace=inplace, limit_direction=limit_direction, limit_area=limit_area, downcast=downcast)
#     pdf.ffill(inplace=True)
#     pdf.reset_index(drop=False, inplace=True)
#     pdf.sort_index(axis=1, inplace=True)
#     return pdf
# #
# agcc.groupby(["user","version"])
#
#agc.show(100,truncate=False)