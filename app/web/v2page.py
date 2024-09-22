import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from fastapi import Request, APIRouter, Query, Depends
from fastapi.encoders import jsonable_encoder
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from app.core.database import SqlSession
from app.core.internal import paginate_info, get_month_start_end
from app.crud import switches_mapper, keyword_mapper, icgb_mapper
from app.model.assembler import convert_vo
from app.model.domain import Keyword, Switches, KeyCountBO, \
    Icgb
from app.model.vo import KeywordVO, CalendarVO

templates = Jinja2Templates(directory='ui/v2')

v2_page_router = APIRouter(prefix='')

def format_with_tolerance(value):
    base_value, tolerance, unit = value
    if base_value is None or base_value == '':
        return f'-{unit}'
    elif tolerance is None or tolerance == '':
        return f'{base_value}{unit}'
    else:
        return f'{base_value}{tolerance}{unit}'

def format_studio_with_manufacturer(value):
    studio, manufacturer = value
    if studio and manufacturer:
        if studio == manufacturer:
            return f'{studio}'
        else:
            return f'{studio} | {manufacturer}'
    elif studio or manufacturer:
        return f'{studio}{manufacturer}'
    else:
        return ''

templates.env.filters['format_with_tolerance'] = format_with_tolerance
templates.env.filters['format_studio_with_manufacturer'] = format_studio_with_manufacturer

@v2_page_router.get("/control", response_class=HTMLResponse)
@v2_page_router.get('/control/main', response_class=HTMLResponse)
async def index(request: Request):
    with SqlSession() as session:
        box_list = get_keyword_counts(session, 'stor_loc_box')
        t = session.count(switches_mapper.count())
    return templates.TemplateResponse('switches-list.html', context={'request': request, 'total': t, 'box_list': box_list})


def get_keyword_counts(sql_session, type, offset=None, limit=None, search=None):
    key_count_list = sql_session.fetchall(switches_mapper.group_by_type(type), KeyCountBO)
    count_detail_map = {}
    for count_detail in key_count_list:
        count_detail_map[count_detail.key] = count_detail.count

    keywords = sql_session.fetchall(keyword_mapper.list_by_type(type, offset, limit, search), KeywordVO)
    for model in keywords:
        model.count = count_detail_map[model.word] if count_detail_map.keys().__contains__(model.word) else 0
    return keywords


@v2_page_router.get("/control/switches", response_class=HTMLResponse)
@v2_page_router.get("/control/switches/{id}", response_class=HTMLResponse)
async def index(request: Request, id: Optional[int]=None):
    with SqlSession() as session:
        switches = Switches(name='', studio='')
        if id is not None:
            switches = session.fetchone(switches_mapper.get_by_id(id), Switches)
        types, manufacturers, marks, studios = keyword_mapper.fetch_text(session)
        stor_loc_boxs = get_keyword_counts(session, 'stor_loc_box')
    return templates.TemplateResponse('switches.html', context={
        'request': request,
        'switches': switches,
        'switch_types': types,
        'manufacturers': manufacturers,
        'stor_loc_boxs': stor_loc_boxs,
        'marks': marks,
        'studios': studios,
        'error_msg': []
    })

@v2_page_router.get("/control/keyword", response_class=HTMLResponse)
async def keyword(request: Request):
    return templates.TemplateResponse('keyword.html', context={'request': request})


@v2_page_router.get("/main")
@v2_page_router.get('/main/{page}')
async def dev(
        request: Request,
        page: Optional[int]=1,
        size: Optional[int]=15
):
    with SqlSession() as session:
        stmt_list, stmt_count = switches_mapper.filter((page - 1) * size, size, None, None, None, True)
        list = session.fetchall(stmt_list, Switches)
        total = session.count(stmt_count)
        manufacturers = session.fetchall(keyword_mapper.list_by_type('manufacturer'), Keyword)
    return templates.TemplateResponse('dev.html', context={
        'request': request,
        'list': [convert_vo(i).dict() for i in list],
        'page': paginate_info(total, page, size),
        'manufacturers': manufacturers
    })

def determine_page_size(request: Request, size: int=Query(None)) -> int:
    user_agent = request.headers.get("User-Agent", "")
    if size is not None:
        return size
    mobile_pattern = re.compile(r"Mobi|Android|iPhone|iPad|iPod|Windows Phone", re.I)
    return 8 if bool(mobile_pattern.search(user_agent)) else 15

@v2_page_router.get("/")
@v2_page_router.get('/collections')
@v2_page_router.get("/collections/")
@v2_page_router.get("/collections/switches")
@v2_page_router.get("/collections/switches/")
@v2_page_router.get("/collections/switches/{page}")
async def main(
        request: Request,
        page: Optional[int]=1,
        size: int=Depends(determine_page_size),
        search: str=Query(default=None, alias='s'),
        type: str=Query(default=None, alias='t'),
        stor_box: Optional[str]=None,
        manufacturer: Optional[str]=None,
        is_available: Optional[int]=1
):
    with SqlSession() as session:
        if is_available == 1:
            available = True
        elif is_available == 2:
            available = False
        else:
            available = None
        stmt_list, stmt_count = switches_mapper.filter((page - 1) * size, size, search, stor_box, manufacturer,
                                                       available, type=type)
        list = session.fetchall(stmt_list, Switches)
        total = session.count(stmt_count)
        types, manufacturers, _, studios = keyword_mapper.fetch_text(session)
        hot_switches = switches_mapper.fetch_hot(session, size=3)
    return templates.TemplateResponse('collections-switches.html', context={
        'request': request,
        'list': [convert_vo(i).dict() for i in list],
        'page': paginate_info(total, page, size),
        'manufacturers': manufacturers,
        'switches_types': types,
        'hot_switches': hot_switches,
    })

@v2_page_router.get('/icgb')
async def ic(request: Request):
    with SqlSession() as session:
        start, end = get_month_start_end(datetime.now())
        list = session.fetchall(icgb_mapper.list_by_time(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")), Icgb)
        # events = [CalendarVO(title=data.title, start=data.icgb_day, end=data.icgb_day, url=data.href) for data in list]
    return templates.TemplateResponse('icgb.html', context={
        'request': request,
        # 'events': jsonable_encoder(events)
    })

@v2_page_router.get('/control/ig')
async def ayb(request: Request,):
    yesterday = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    with SqlSession() as session:
        list = session.fetchall(icgb_mapper.list_by_day(day=yesterday), Icgb)
        days = session.fetchall(icgb_mapper.list_day(), Icgb)
        if len(list) <= 0:
            icgblist, day = icgb_mapper.gen_icgb(0)
            if len(icgblist) > 0:
                session.execute(icgb_mapper.batch_save_or_update(icgblist))
                list = session.fetchall(icgb_mapper.list_by_day(day=day), Icgb)
            else:
                list = [Icgb(title=day)]
    return templates.TemplateResponse('c-ig.html', context={
        'request': request,
        'list': list,
        'day': day if len(list) <= 0 else yesterday,
        'days': jsonable_encoder([d.day for d in days])
    })

@v2_page_router.get('/control/sqlite')
async def sqlite(request: Request):
    return templates.TemplateResponse('sqlite.html', context={
        'request': request,
    })

@v2_page_router.get('/control/keyboard')
async def keyboard(request:Request):
    with SqlSession() as session:
        list = switches_mapper.list(session)
    return templates.TemplateResponse('keyboard.html', context={
        'request': request,
        'list': [s.name for s in list]
    })

@v2_page_router.get('/collections/products/{id}')
async def detail(request: Request, id: int):
    with SqlSession() as session:
        model = session.fetchone(switches_mapper.get_by_id(id), Switches)
    return templates.TemplateResponse('collections-products.html', context={
        'request': request,
        'switch': convert_vo(model).dict()
    })

@v2_page_router.get('/collections/keyboard')
@v2_page_router.get('/collections/keyboard/')
@v2_page_router.get('/collections/keyboard/{keyboard}')
async def keyboard(request: Request, keyboard:Optional[str] = 'D.1', mode:Optional[str] = 't'):
    with SqlSession() as session:
        stmt_list, _ = switches_mapper.filter(start=0, length=1000, stor_box=keyboard)
        list = session.fetchall(stmt_list, Switches)
        array_2d = generate_2d_array(list)
        stor_boxs = keyword_mapper.fetch_keyboard(session)
    return templates.TemplateResponse('collections-keyboard.html', context={
        'request': request,
        'data': array_2d,
        'stor_boxs': stor_boxs,
    })


def generate_2d_array(data: List[Switches]):
    # 查找数据中的最大行和列索引
    max_row = max((item.stor_loc_row for item in data if item.stor_loc_row is not None), default=0)
    max_column = max((item.stor_loc_col for item in data if item.stor_loc_col is not None), default=0)

    # 初始化一个空的二维数组
    array_2d = [[None for _ in range(max_column)] for _ in range(max_row)]

    # 填充二维数组
    for item in data:
        if item.stor_loc_row is not None and item.stor_loc_col is not None:
            row = item.stor_loc_row
            column = item.stor_loc_col
            array_2d[row-1][column-1] = item.dict()

    return array_2d



