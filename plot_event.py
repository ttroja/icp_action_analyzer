#!/usr/bin/env python2
# -*- coding: UTF-8 -*-

import os,sys,json,re,math
import argparse
import matplotlib
matplotlib.use('Agg') # Tcl_AsyncDelete: cannot find async handler
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

EYECLOSE_FROM_3IN1 = True

TAG_NORMAL_ACTION          = 'update_score'
TAG_EYECLOSE_ACTION        = 'eyeclose_score'

ATTR_TAG                   = "tag"
ATTR_ACTION_NAME           = "action_name"
ATTR_FRAME_ID              = "frame_id"
ATTR_SCORE                 = "score"
ATTR_START_THRESHOLD       = "start_threshold"
ATTR_ACTION_THRESHOLD      = "action_threshold"
ATTR_END_THRESHOLD         = "end_threshold"
ATTR_START_AVERAGE         = "start_average"
ATTR_ACTION_AVERAGE        = "action_average"
ATTR_END_AVERAGE           = "end_average"

ATTR_EYE_DISTANCE          = "distance"
ATTR_EYE_MAX_DISTANCE      = "max_eye_distance"
ATTR_EYE_LEFT              = "left"
ATTR_EYE_RIGHT             = "right"

ACTION_NAME_YAW            = "yawn"
ACTION_NAME_SMOKE          = "smoke"
ACTION_NAME_DRINK          = "drink"
ACTION_NAME_PHONE_CALL     = "phone_call"
ACTION_NAME_EYE_CLOSE      = "eye_close"
ACTION_NAME_EYE_CLOSE_DIS  = "eye_close_distance" # need be merged into eye_close
ACTION_NAME_DISTRACTION    = "distraction"

CONSTANT_ROW               = 2

def get_file_name(path):
    """
    video path /home/likeyu/useky/atp/../work/cache/20/71/54c6863e7280a62845aa50b23334
    video path /home/root/useky/atp/../work/cache/00/53/e5cb42aecc0554d0353b631cbe1e
    video path /home/cyh/Downloads/dataset/dataset/8edc71a72b02727d8ba075bc172e18f1.mp4
    """
    path = path.replace("\n", "")
    tmp = ""
    if ".mp4" in path:
        tmp = os.path.split(path)[-1]
        tmp = tmp.replace(".mp4", "")
    else:
        
        tmp = path.split()[-1]
        tmp = tmp.split("cache")[-1]
        tmp = tmp.replace('/','')
    return tmp

# map_video_jsonlist{"video_name":[{"yawn"},{"smoke"}...{"yawn"},{"smoke"}]}
def load_log_file(data_path):
    pattern = "^\{.*\}"
    f = open(data_path, "r")
    lines = f.readlines()
    f.close()

    map_video_jsonlist = {}
    current_video_name = ""

    for line in lines:
        if current_video_name != "" and re.search(pattern, line):
            obj = json.loads(re.search(pattern, line).group(0))
            map_video_jsonlist[current_video_name].append(obj)
            continue
        if "video path" in line:
            current_video_name = get_file_name(line)
            if current_video_name != "" and current_video_name not in map_video_jsonlist.keys():
                map_video_jsonlist[current_video_name] = []

    return map_video_jsonlist

# map_video_actions{"video_name":{"eye_close":[[json_obj1,json_obj2...], "eye_close_distance":[json_obj1,json_obj2...],...}, "video_name":{...}}
def normalize_json_data(map_video_jsonlist):
    map_video_actions = {}
    for video_name in map_video_jsonlist.keys():
        json_list = map_video_jsonlist[video_name]
        map_video_actions[video_name] = {}
        for json_obj in json_list:
            tag = json_obj["tag"]
            if tag == TAG_EYECLOSE_ACTION:
                action_name = ACTION_NAME_EYE_CLOSE_DIS
            else:
                action_name = json_obj[ATTR_ACTION_NAME]
            if action_name not in map_video_actions[video_name].keys():
                map_video_actions[video_name][action_name] = []
            map_video_actions[video_name][action_name].append(json_obj)
    return map_video_actions

# len(eye_close) > len(eye_close_distance), no face tracked could update_score, but do not have distance info, merge eye_close into eye_close_distance
def merge_eyeclose_data(map_video_actions):
    for video_name in map_video_actions.keys():
        eye_close_list = []
        eye_close_dis_list = []

        if ACTION_NAME_EYE_CLOSE in map_video_actions[video_name].keys():
            eye_close_list = map_video_actions[video_name][ACTION_NAME_EYE_CLOSE]
        if ACTION_NAME_EYE_CLOSE_DIS in map_video_actions[video_name].keys():
            eye_close_dis_list = map_video_actions[video_name][ACTION_NAME_EYE_CLOSE_DIS]
        merged_eye_close_list = []
        for json_obj in eye_close_dis_list:
            frame_id = json_obj[ATTR_FRAME_ID]
            match = False
            for obj in eye_close_list:
                if obj[ATTR_FRAME_ID] == frame_id:
                    json_obj[ATTR_ACTION_NAME]      = ACTION_NAME_EYE_CLOSE
                    json_obj[ATTR_START_THRESHOLD]  = obj[ATTR_START_THRESHOLD]
                    json_obj[ATTR_ACTION_THRESHOLD] = obj[ATTR_ACTION_THRESHOLD]
                    json_obj[ATTR_END_THRESHOLD]    = obj[ATTR_END_THRESHOLD]
                    json_obj[ATTR_START_AVERAGE]    = obj[ATTR_START_AVERAGE]
                    json_obj[ATTR_ACTION_AVERAGE]   = obj[ATTR_ACTION_AVERAGE]
                    json_obj[ATTR_END_AVERAGE]      = obj[ATTR_END_AVERAGE]
                    match = True
            if match:# some log is not complete in multi thread
                merged_eye_close_list.append(json_obj)
        if ACTION_NAME_EYE_CLOSE in map_video_actions[video_name].keys():
            del map_video_actions[video_name][ACTION_NAME_EYE_CLOSE]
        if ACTION_NAME_EYE_CLOSE_DIS in map_video_actions[video_name].keys():
            del map_video_actions[video_name][ACTION_NAME_EYE_CLOSE_DIS]
        map_video_actions[video_name][ACTION_NAME_EYE_CLOSE] = merged_eye_close_list
    return

# map_video_actions{"video_name":{"eye_close":[[json_obj1,json_obj2...], "eye_close_distance":[json_obj1,json_obj2...],...}, "video_name":{...}}
# plot_data {"video_name": {"smoke":{"list_x":[list_x], "list_y":[list_y], ...}, {"yawn":{"list_x":[list_x], "list_y":[list_y], ...}, ...}, "video_name":... }
def normalize_plot_data(map_video_actions):
    plot_data = {}
    for video_name in map_video_actions:
        plot_data[video_name] = {}
        video_dict = map_video_actions[video_name]
        for action_name in video_dict:
            plot_data[video_name][action_name] = {}
            action_list = video_dict[action_name]

            data_frame_id         = []
            data_score            = []
            data_start_threshold  = []
            data_action_threshold = []
            data_end_threshold    = []
            data_start_average    = []
            data_action_average   = []
            data_end_average      = []
            data_distance         = []
            data_max_eye_distance = []
            data_left             = []
            data_right            = []

            for action_obj in action_list:
                #print action_obj
                data_frame_id.append(action_obj[ATTR_FRAME_ID])
                data_score.append(action_obj[ATTR_SCORE])
                data_start_threshold.append(action_obj[ATTR_START_THRESHOLD])
                data_action_threshold.append(action_obj[ATTR_ACTION_THRESHOLD])
                data_end_threshold.append(action_obj[ATTR_END_THRESHOLD])
                data_start_average.append(action_obj[ATTR_START_AVERAGE])
                data_action_average.append(action_obj[ATTR_ACTION_AVERAGE])
                data_end_average.append(action_obj[ATTR_END_AVERAGE])
                if action_name == ACTION_NAME_EYE_CLOSE and EYECLOSE_FROM_3IN1:
                    data_distance.append(action_obj[ATTR_EYE_DISTANCE])
                    data_max_eye_distance.append(action_obj[ATTR_EYE_MAX_DISTANCE])
                    data_left.append(action_obj[ATTR_EYE_LEFT])
                    data_right.append(action_obj[ATTR_EYE_RIGHT])
        
            plot_data[video_name][action_name][ATTR_FRAME_ID]         = data_frame_id
            plot_data[video_name][action_name][ATTR_SCORE]            = data_score
            plot_data[video_name][action_name][ATTR_START_THRESHOLD]  = data_start_threshold
            plot_data[video_name][action_name][ATTR_ACTION_THRESHOLD] = data_action_threshold
            plot_data[video_name][action_name][ATTR_END_THRESHOLD]    = data_end_threshold
            plot_data[video_name][action_name][ATTR_START_AVERAGE]    = data_start_average
            plot_data[video_name][action_name][ATTR_ACTION_AVERAGE]   = data_action_average
            plot_data[video_name][action_name][ATTR_END_AVERAGE]      = data_end_average
            if action_name == ACTION_NAME_EYE_CLOSE and EYECLOSE_FROM_3IN1:
                plot_data[video_name][action_name][ATTR_EYE_DISTANCE]         = data_distance
                plot_data[video_name][action_name][ATTR_EYE_MAX_DISTANCE]     = data_max_eye_distance
                plot_data[video_name][action_name][ATTR_EYE_LEFT]             = data_left
                plot_data[video_name][action_name][ATTR_EYE_RIGHT]            = data_right
    return plot_data

def plot_normal_action(video_data, label_x, label_y, save_path, grid=False):
    data_frame  = video_data[ATTR_FRAME_ID]
    data_score  = video_data[ATTR_SCORE]
    data_start  = video_data[ATTR_START_THRESHOLD]
    data_action = video_data[ATTR_ACTION_THRESHOLD]
    data_end    = video_data[ATTR_END_THRESHOLD]
    data_start_average = video_data[ATTR_START_AVERAGE]

    plt.figure(figsize=(7.5,6))
    plt.plot(data_frame, data_score, 'k-', label="score")
    plt.plot(data_frame, data_start, 'r-', label="start")
    plt.plot(data_frame, data_action, 'g-', label="action")
    plt.plot(data_frame, data_end, 'b-', label="end")
    plt.plot(data_frame, data_start_average, 'y', label="average")
    plt.ylabel(label_y)
    plt.xlabel(label_x)
    #plt.title(video_name)
    if grid:
        plt.xticks(range(1,data_frame[-1],1))
        plt.grid()
    plt.legend()
    #plt.show()
    plt.savefig(save_path)
    plt.close()

def plot_eye_close(video_data, label_x, label_y, save_path, grid=False):
    data_frame  = video_data[ATTR_FRAME_ID]
    data_score  = video_data[ATTR_SCORE]
    data_start  = video_data[ATTR_START_THRESHOLD]
    data_action = video_data[ATTR_ACTION_THRESHOLD]
    data_end    = video_data[ATTR_END_THRESHOLD]
    data_start_average = video_data[ATTR_START_AVERAGE]

    if EYECLOSE_FROM_3IN1:
        fig = plt.figure(1, figsize=(7.5,6))
        gridspec.GridSpec(5,1)

        plt.subplot2grid((5,1), (0,0), colspan=1, rowspan=2)
        data_dis    = video_data[ATTR_EYE_DISTANCE]
        data_max_dis= video_data[ATTR_EYE_MAX_DISTANCE]
        data_left   = video_data[ATTR_EYE_LEFT]
        data_right  = video_data[ATTR_EYE_RIGHT]

        #plt.plot(data_frame, data_dis, 'c-', label="distance")
        plt.plot(data_frame, data_max_dis, 'm-', label="max_distance")
        plt.plot(data_frame, data_left, 'C2-', label="left")
        plt.plot(data_frame, data_right, 'C5-', label="right")
        plt.legend()

        plt.subplot2grid((5,1), (2,0), colspan=1, rowspan=3)
        plt.plot(data_frame, data_score, 'k-', label="score")
        plt.plot(data_frame, data_start, 'r-', label="start")
        plt.plot(data_frame, data_action, 'g-', label="action")
        plt.plot(data_frame, data_end, 'b-', label="end")
        plt.plot(data_frame, data_start_average, 'y', label="start_average")
    else:
        plt.figure(figsize=(7.5,6))
        plt.plot(data_frame, data_score, 'k-', label="score")
        plt.plot(data_frame, data_start, 'r-', label="start")
        plt.plot(data_frame, data_action, 'g-', label="action")
        plt.plot(data_frame, data_end, 'b-', label="end")
        plt.plot(data_frame, data_start_average, 'y', label="average")
        plt.legend()
    plt.ylabel(label_y)
    plt.xlabel(label_x)
    #plt.title(video_name)
    if grid:
        plt.xticks(range(1,data_frame[-1],1))
        plt.grid()
    #plt.show()
    plt.savefig(save_path)
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", help="log file path")
    parser.add_argument("--action", choices=["yawn", "smoke", "drink", "phone_call", "eye_close"], help="action for plot")
    parser.add_argument("--video", help="video name for show up")

    args = vars(parser.parse_args())

    file_path     = args["path"]
    action_name   = args["action"].strip()
    video_name    = args["video"].strip()

    if video_name == "" or action_name == "":
        raise Exception("invalid arg: video_name: %s, action_name: %s" % (video_name, action_name))
    else:
        map_video_jsonlist = load_log_file(file_path)

        map_video_actions = normalize_json_data(map_video_jsonlist)

        merge_eyeclose_data(map_video_actions)

        plot_data = normalize_plot_data(map_video_actions)

        if video_name not in plot_data.keys():
            raise Exception("video_name not exists, %s" % video_name)
        if action_name not in plot_data[video_name].keys():
            raise Exception("action_name not exists, %s, %s" % (video_name, action_name))
        
        video_data  = plot_data[video_name][action_name]

        print "plot ..."

        if action_name == ACTION_NAME_EYE_CLOSE:
            plot_eye_close(video_data, ATTR_FRAME_ID, ATTR_SCORE, video_name)
        else:
            plot_normal_action(video_data, ATTR_FRAME_ID, ATTR_SCORE, video_name)