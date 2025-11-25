from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    The main menu keyboard with the two core functions.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Генерация карточки", callback_data="start_card_generation")],
        [InlineKeyboardButton(text="📸 Обработка фото", callback_data="start_photo_processing")],
        [InlineKeyboardButton(text="💰 Мой баланс / Купить кредиты", callback_data="show_main_menu")]
    ])


def create_card_generation_keyboard() -> InlineKeyboardMarkup:
    """The keyboard for the card generation process."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel_card_generation")]
    ])


def create_photo_processing_keyboard() -> InlineKeyboardMarkup:
    """The keyboard for the photo processing flow."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel_photo_processing")]
    ])


def create_photo_upload_keyboard() -> InlineKeyboardMarkup:
    """The keyboard for when user is uploading photos."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data="photos_done")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel_photo_processing")]
    ])

def back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    """A keyboard with a single button to go back to the main menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")]
    ])
