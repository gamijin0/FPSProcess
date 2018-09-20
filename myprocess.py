import copy
import base64
import random
import string
import xml.etree.ElementTree as ET
import os
import json
from uuid import uuid4
import zipfile, os
from collections import OrderedDict
import shutil

INT_ID = 1


def get_zip_file(input_path, result):
    """
    对目录进行深度优先遍历
    :param input_path:
    :param result:
    :return:
    """
    files = os.listdir(input_path)
    for file in files:
        if os.path.isdir(input_path + '/' + file):
            get_zip_file(input_path + '/' + file, result)
        else:
            result.append(input_path + '/' + file)


def zip_file_path(input_path, output_path, output_name):
    """
    压缩文件
    :param input_path: 压缩的文件夹路径
    :param output_path: 解压（输出）的路径
    :param output_name: 压缩包名称
    :return:
    """
    f = zipfile.ZipFile(os.path.join(output_path, output_name), 'w', zipfile.ZIP_DEFLATED)
    filelists = []
    get_zip_file(input_path, filelists)
    for file in filelists:
        f.write(file)
    # 调用了close方法才会保证完成压缩
    f.close()
    return output_path + r"/" + output_name


class FPSParser(object):
    def __init__(self, fps_path):
        self.fps_path = fps_path

    @property
    def _root(self):
        root = ET.ElementTree(file=self.fps_path).getroot()
        version = root.attrib.get("version", "No Version")
        if version not in ["1.1", "1.2"]:
            raise ValueError("Unsupported version '" + version + "'")
        return root

    def parse(self):
        ret = []
        for node in self._root:
            if node.tag == "item":
                ret.append(self._parse_one_problem(node))
        return ret

    def _parse_one_problem(self, node):
        sample_start = True
        test_case_start = True
        problem = {
            "title": "No Title",
            "description": "No Description",
            "input": "No Input Description",
            "output": "No Output Description",
            "memory_limit": {"unit": None, "value": None},
            "time_limit": {"unit": None, "value": None},
            "samples": [],
            "images": [],
            "append": [],
            "template": [],
            "prepend": [],
            "test_cases": [],
            "hint": None,
            "source": None,
            "spj": None,
            "solution": []
        }
        for item in node:
            tag = item.tag
            if tag in ["title", "description", "input", "output", "hint", "source"]:
                problem[item.tag] = item.text
            elif tag == "time_limit":
                unit = item.attrib.get("unit", "s")
                if unit not in ["s", "ms"]:
                    raise ValueError("Invalid time limit unit")
                problem["time_limit"]["unit"] = item.attrib.get("unit", "s")
                value = int(item.text)
                if value <= 0:
                    raise ValueError("Invalid time limit value")
                problem["time_limit"]["value"] = value
            elif tag == "memory_limit":
                unit = item.attrib.get("unit", "MB")
                if unit not in ["MB", "KB", "mb", "kb"]:
                    raise ValueError("Invalid memory limit unit")
                problem["memory_limit"]["unit"] = unit.upper()
                value = int(item.text)
                if value <= 0:
                    raise ValueError("Invalid memory limit value")
                problem["memory_limit"]["value"] = value
            elif tag in ["template", "append", "prepend", "solution"]:
                lang = item.attrib.get("language")
                if not lang:
                    raise ValueError("Invalid " + tag + ", language name is missed")
                if tag == 'solution':
                    if lang not in ['Pascal','C#']:
                        if lang == 'Python':
                            lang = 'Python2'
                        problem[tag].append({"language": lang, "code": item.text})

            elif tag == 'spj':
                lang = item.attrib.get("language")
                if not lang:
                    raise ValueError("Invalid spj, language name if missed")
                problem["spj"] = {"language": lang, "code": item.text}
            elif tag == "img":
                problem["images"].append({"src": None, "blob": None})
                for child in item:
                    if child.tag == "src":
                        problem["images"][-1]["src"] = child.text
                    elif child.tag == "base64":
                        problem["images"][-1]["blob"] = base64.b64decode(child.text)
            elif tag == "sample_input":
                if not sample_start:
                    raise ValueError("Invalid xml, error 'sample_input' tag order")
                problem["samples"].append({"input": item.text, "output": None})
                sample_start = False
            elif tag == "sample_output":
                if sample_start:
                    raise ValueError("Invalid xml, error 'sample_output' tag order")
                problem["samples"][-1]["output"] = item.text
                sample_start = True
            elif tag == "test_input":
                if not test_case_start:
                    raise ValueError("Invalid xml, error 'test_input' tag order")
                problem["test_cases"].append({"input": item.text, "output": None})
                test_case_start = False
            elif tag == "test_output":
                if test_case_start:
                    raise ValueError("Invalid xml, error 'test_output' tag order")
                problem["test_cases"][-1]["output"] = item.text
                test_case_start = True

        return problem


class QDUOJ_OBJ:
    data = {}

    def __init__(self, problem: dict, save_path="qduoj_data", tag=["算法"]):
        self._problem = problem
        self.save_path = save_path
        self.data = OrderedDict([
            ('display_id', self._problem['display_id']),
            ('title', self._problem['title']),
            ('description', {"format": "html", "value": self._problem['description']}),
            ('tags', tag),
            ('input_description', {
                "format": "html",
                "value": self._problem['input']
            }),
            ('output_description', {
                "format": "html",
                "value": self._problem['output']
            }),
            ('test_case_score', None),
            ('hint', {
                "format": "html",
                "value": ""
            }),
            ('time_limit', 1000),
            ('memory_limit', 256),
            ('samples', self._problem['samples']),
            ('template', {}),
            ('spj', None),
            ('rule_type', "ACM"),
            ('source', "SU Online Judgement http://127.0.0.1"),
            ('answers', self._problem['solution'] if "solution" in self._problem else [])
        ])

    def save_test_case(self, problem, base_dir, input_preprocessor=None, output_preprocessor=None):
        for index, item in enumerate(problem["test_cases"]):
            with open(os.path.join(base_dir, str(index + 1) + ".in"), "w", encoding="utf-8") as f:
                if input_preprocessor:
                    input_content = input_preprocessor(item["input"])
                else:
                    input_content = item["input"]
                f.write(input_content)
            with open(os.path.join(base_dir, str(index + 1) + ".out"), "w", encoding="utf-8") as f:
                if output_preprocessor:
                    output_content = output_preprocessor(item["output"])
                else:
                    output_content = item["output"]
                f.write(output_content)

    def save_flat_file(self, target_dir):
        PATH = ""
        for path in os.path.split(target_dir):
            PATH = os.path.join(PATH, path)
            if not os.path.exists(PATH):
                os.mkdir(PATH)
        global INT_ID
        problem_json = json.dumps(self.data, indent=4)
        with open(os.path.join(target_dir, 'problem.json'), mode='w', encoding='utf-8') as f:
            f.write(problem_json)
        test_case_dir = os.path.join(target_dir, 'testcase')
        if not os.path.exists(test_case_dir):
            os.mkdir(test_case_dir)
        self.save_test_case(self._problem, test_case_dir)
        print("Saved :" + str(INT_ID))
        INT_ID += 1

    def save_zipfile(self):
        global INT_ID
        print("Zipped :" + str(INT_ID))
        tmp_dir = "1"
        self.save_flat_file(tmp_dir)
        # shutil.make_archive(os.path.join(self.save_path, str(uuid4())[:8]), 'zip', target_dir)
        zip_file_path(tmp_dir, self.save_path, str(uuid4())[:8] + '.zip')
        shutil.rmtree(tmp_dir)  # 递归删除文件夹


def get_pids_from_fname(fname: str):
    back = fname.split('-')[2]
    front = back.split('.')[0]
    pids = front.split(',')
    return pids


if (__name__ == "__main__"):
    SKIP = 0
    skip = 0

    QDUOJ_FILE_DIR = 'qduoj_file'

    for fname in os.listdir("tmp"):
        pids = get_pids_from_fname(fname)
        print(pids)
        parser = FPSParser("tmp/" + fname)
        problems = parser.parse()
        for index, p in enumerate(problems):
            p['display_id'] = str(pids[index])
            print("Get problem:" + str(p['display_id']))
            qobj = QDUOJ_OBJ(p)
            qobj.save_flat_file(os.path.join(QDUOJ_FILE_DIR, str(INT_ID)))

    shutil.make_archive('upload', 'zip', QDUOJ_FILE_DIR, )
