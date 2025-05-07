import logging
import random
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile


from dotenv import load_dotenv
import os

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


ANIMALS = ['owl', 'elephant', 'bear', 'zebra', 'turtle', 'lemur', 'parrot']
QUESTIONS = [
    {
        'text': "Где вы хотели бы провести выходные?",
        'options': ["На берегу реки", "В горах", "В зелёном лесу", "В городской черте"],
        'weights': [
            {'owl':1,'elephant':0,'bear':0,'zebra':0,'turtle':2,'lemur':1,'parrot':0},
            {'owl':0,'elephant':2,'bear':1,'zebra':0,'turtle':0,'lemur':0,'parrot':0},
            {'owl':0,'elephant':0,'bear':0,'zebra':1,'turtle':2,'lemur':1,'parrot':0},
            {'owl':0,'elephant':0,'bear':1,'zebra':2,'turtle':0,'lemur':0,'parrot':1},
        ]
    },
    {
        'text': "Какой ваш любимый тип еды?",
        'options': ["Растительный", "Мясной", "Сладкий", "Разнообразный"],
        'weights': [
            {'owl':2,'elephant':0,'bear':0,'zebra':0,'turtle':1,'lemur':2,'parrot':1},
            {'owl':0,'elephant':2,'bear':2,'zebra':0,'turtle':0,'lemur':0,'parrot':1},
            {'owl':1,'elephant':0,'bear':0,'zebra':1,'turtle':2,'lemur':1,'parrot':2},
            {'owl':1,'elephant':1,'bear':1,'zebra':2,'turtle':0,'lemur':0,'parrot':1},
        ]
    },
    {
        'text': "С какой скоростью вы предпочитаете двигаться в жизни?",
        'options': ["Медленно и вдумчиво", "Быстро по плану", "Нестандартно как ветер", "В своём темпе"],
        'weights': [
            {'owl':1,'elephant':0,'bear':2,'zebra':0,'turtle':3,'lemur':1,'parrot':0},
            {'owl':0,'elephant':3,'bear':2,'zebra':1,'turtle':0,'lemur':0,'parrot':1},
            {'owl':0,'elephant':0,'bear':0,'zebra':3,'turtle':0,'lemur':2,'parrot':2},
            {'owl':1,'elephant':1,'bear':1,'zebra':0,'turtle':0,'lemur':2,'parrot':1},
        ]
    },
]


class QuizStates(StatesGroup):
    Q1 = State()
    Q2 = State()
    Q3 = State()
    RESULT = State()


async def send_question(chat: types.Message | types.CallbackQuery, q_index: int):
    logger.info(f"📋 Отправляю вопрос #{q_index+1}")
    try:
        q = QUESTIONS[q_index]
        builder = InlineKeyboardBuilder()
        for idx, opt in enumerate(q['options']):
            builder.button(text=opt, callback_data=f"answer:{q_index}:{idx}")
        builder.adjust(1)
        markup = builder.as_markup()
        if isinstance(chat, types.Message):
            await chat.answer(q['text'], reply_markup=markup)
        else:
            await chat.message.answer(q['text'], reply_markup=markup)
    except Exception:
        logger.exception(f"Ошибка при отправке вопроса #{q_index+1}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(scores={animal: 0 for animal in ANIMALS})
    await message.answer(
        "👋 Привет! Добро пожаловать в викторину «Какое у вас тотемное животное?»\nПоехали!"
    )
    await state.set_state(QuizStates.Q1)
    await send_question(message, 0)

@dp.callback_query(lambda c: c.data.startswith("answer"))
async def process_answer(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    q_idx, opt_idx = map(int, callback.data.split(':')[1:])
    data = await state.get_data()
    scores = data.get('scores', {})
    for animal, w in QUESTIONS[q_idx]['weights'][opt_idx].items():
        scores[animal] = scores.get(animal, 0) + w
    await state.update_data(scores=scores)

    next_q = q_idx + 1
    if next_q < len(QUESTIONS):
        await state.set_state(list(QuizStates)[next_q])
        await send_question(callback, next_q)
    else:
        top = max(scores.values())
        winners = [a for a, v in scores.items() if v == top]
        result = random.choice(winners)
        names = {
            'owl': 'Сова',
            'elephant': 'Азиатский слон',
            'bear': 'Бурый медведь',
            'zebra': 'Зебра Греви',
            'turtle': 'Лучистая черепаха',
            'lemur': 'Лемур',
            'parrot': 'Благородный зелёно-красный попугай',
        }
        name_ru = names.get(result, result.capitalize())
        text = (
            f"🎉 Ваше тотемное животное: *{name_ru}*! 🎉\nУзнайте больше и станьте опекуном."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="Узнать больше об опеке 🧡", url="https://moscowzoo.ru/about/guardianship")
        builder.button(text="Попробовать ещё раз 🔄", callback_data="restart")
        builder.button(text="Поделиться в Telegram 📢", switch_inline_query="")
        builder.adjust(1)
        markup = builder.as_markup()

        photo_path = f"images/{result}.jpg"
        try:
            photo = FSInputFile(photo_path)
            await bot.send_photo(
                callback.from_user.id,
                photo=photo,
                caption=text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        except Exception as e:
            await bot.send_message(
                callback.from_user.id,
                text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        await state.clear()

@dp.callback_query(lambda c: c.data == "restart")
async def process_restart(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await cmd_start(callback.message, state)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("/start — начать викторину\n/help — справка\n/feedback — отзыв")

@dp.message(Command("feedback"))
async def cmd_feedback(message: types.Message):
    await message.answer("Отправьте ваш отзыв, мы учтём его!")


async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
