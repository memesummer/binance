# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2025/4/15 16:15
#    @Description   : 
#
# ===============================================================
import requests

# RootData API 配置
API_KEY = "VyQzL3aLCgh0c1pnF7DHrMhv07dfOcOg"  # 替换为你的 RootData API Key
BASE_URL = "https://api.rootdata.com"
SEARCH_ENDPOINT = "/open/ser_inv"  # 搜索投资信息的端点
DETAIL_ENDPOINT = "/open/get_item"  # 获取项目详细信息的端点
LANGUAGE = "cn"  # 语言设置为英文（可改为 "cn" 使用中文）

# 请求头
headers = {
    "apikey": API_KEY,
    "language": LANGUAGE,
    "Content-Type": "application/json"
}


def format_number(num):
    if abs(num) >= 1000000000:  # 10亿
        return f"{num / 1000000000:.2f}B"
    elif abs(num) >= 1000000:
        return f"{num / 1000000:.2f}M"
    elif abs(num) >= 1000:
        return f"{num / 1000:.2f}K"
    else:
        return str(num)


# 第一步：搜索投资信息，获取 type=1 的项目 ID
def search_investments(query):
    payload = {"query": query}
    try:
        response = requests.post(
            BASE_URL + SEARCH_ENDPOINT,
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()

        if data.get("result") == 200:
            investments = data.get("data", [])
            # 筛选 type=1 的项目 ID
            for inv in investments:
                if inv.get("type") == 1:
                    return inv.get("id")
        else:
            print(f"搜索投资信息失败: {data.get('message', '未知错误')}")
            return []

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP 错误 (搜索): {http_err}")
        return []
    except requests.exceptions.ConnectionError:
        print("网络连接错误，请检查网络 (搜索)")
        return []
    except requests.exceptions.Timeout:
        print("请求超时 (搜索)")
        return []
    except requests.exceptions.RequestException as err:
        print(f"请求错误 (搜索): {err}")
        return []
    except ValueError:
        print("响应格式错误，无法解析 JSON (搜索)")
        return []


# 第二步：根据项目 ID 获取详细信息
def get_project_details(project_id):
    payload = {
        "project_id": project_id,
        "include_team": True,
        "include_investors": True
    }
    try:
        response = requests.post(
            BASE_URL + DETAIL_ENDPOINT,
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()

        if data.get("result") == 200:
            return data.get("data", {})
        else:
            print(f"获取项目 {project_id} 详情失败: {data.get('message', '未知错误')}")
            return None

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP 错误 (详情): {http_err}")
        return None
    except requests.exceptions.ConnectionError:
        print("网络连接错误，请检查网络 (详情)")
        return None
    except requests.exceptions.Timeout:
        print("请求超时 (详情)")
        return None
    except requests.exceptions.RequestException as err:
        print(f"请求错误 (详情): {err}")
        return None
    except ValueError:
        print("响应格式错误，无法解析 JSON (详情)")
        return None


# 显示项目详细信息
def display_project_details(project):
    if project:
        res = ""
        res += f"🔐*项目名称*: {project.get('project_name', 'N/A')}\n"
        res += f"💠*代币符号*: {project.get('token_symbol', 'N/A')}\n"
        res += f"📝*简介*: {project.get('one_liner', 'N/A')}\n"
        res += f"🔍*详细介绍*: {project.get('description', 'N/A')}\n"
        res += f"📆*成立时间*: {project.get('establishment_date', 'N/A')}\n"
        res += f"💰*融资总额*: {format_number(project.get('total_funding', 'N/A'))}\n"
        res += f"⛓*项目标签*: {project.get('tags', 'N/A')}\n"

        # 显示投资机构信息
        investors = project.get('investors', [])
        if investors:
            res += "\n🏛️*投资机构*：\n"
            ling = ""
            other = ""
            for inv in investors:
                if inv.get('lead_investor', 'N/A') == 1:
                    ling += f"{inv.get('name', 'N/A')} | "
                else:
                    other += f"{inv.get('name', 'N/A')} | "
            res += f"🏦*领投*：{ling}\n🤝*其他*：{other}\n"

        else:
            res += "\n🏛️*投资机构*: 无"

        # 显示相似项目
        sp = project.get('similar_project', [])
        if sp:
            res += "\nℹ️*相似项目*：\n"
            for p in sp:
                res += f"   🔐*名称*: {p.get('project_name', 'N/A')}\n"
                res += f"   📝*简介*: {p.get('brief_description', 'N/A')}\n"
                res += "   ---\n"
        else:
            res += "\nℹ️*相似项目*: 无"
        return res

    else:
        return "*未找到项目信息*"


def root_data_meta_data(query):
    project_id = search_investments(query)

    if not project_id:
        return f"*未找到与 '{query}' 相关项目的详细信息*"

    # 第二步：获取项目详细信息
    project_details = get_project_details(project_id)
    return display_project_details(project_details)
