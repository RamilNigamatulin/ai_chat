# Импорт необходимых библиотек и модулей
import flet as ft  # Фреймворк для создания кроссплатформенных приложений с современным UI
from api.openrouter import (
    OpenRouterClient,
)  # Клиент для взаимодействия с AI API через OpenRouter
from ui.styles import AppStyles  # Модуль с настройками стилей интерфейса
from ui.components import (
    MessageBubble,
    ModelSelector,
)  # Компоненты пользовательского интерфейса
from utils.cache import ChatCache  # Модуль для кэширования истории чата
from utils.logger import AppLogger  # Модуль для логирования работы приложения
from utils.analytics import (
    Analytics,
)  # Модуль для сбора и анализа статистики использования
from utils.monitor import (
    PerformanceMonitor,
)  # Модуль для мониторинга производительности
from utils.notifications import NotificationManager  # Модуль для уведомлений о балансе
import asyncio  # Библиотека для асинхронного программирования
import time  # Библиотека для работы с временными метками
import json  # Библиотека для работы с JSON-данными
from datetime import datetime  # Класс для работы с датой и временем
import os  # Библиотека для работы с операционной системой
import subprocess  # Для открытия папки в Linux/Windows


class ChatApp:
    """
    Основной класс приложения чата.
    Управляет всей логикой работы приложения, включая UI и взаимодействие с API.
    """

    def __init__(self):
        """
        Инициализация основных компонентов приложения.
        """
        # Инициализация основных компонентов
        self.api_client = OpenRouterClient()  # Создание клиента для работы с AI API
        self.cache = ChatCache()  # Инициализация системы кэширования
        self.logger = AppLogger()  # Инициализация системы логирования
        self.analytics = Analytics(
            self.cache
        )  # Инициализация системы аналитики с передачей кэша
        self.monitor = PerformanceMonitor()  # Инициализация системы мониторинга
        self.notification_manager = (
            NotificationManager()
        )  # Инициализация менеджера уведомлений

        # Создание компонента для отображения баланса API
        self.balance_text = ft.Text(
            "Баланс: Загрузка...",  # Начальный текст до загрузки реального баланса
            **AppStyles.BALANCE_TEXT,  # Применение стилей из конфигурации
        )
        self.update_balance()  # Первичное обновление баланса и проверка уведомлений

        # Создание директории для экспорта истории чата
        self.exports_dir = "exports"  # Путь к директории экспорта
        os.makedirs(self.exports_dir, exist_ok=True)  # Создание директории, если её нет

    def load_chat_history(self):
        """
        Загрузка истории чата из кэша и отображение её в интерфейсе.
        """
        try:
            history = self.cache.get_chat_history()  # Получение истории из кэша
            for msg in reversed(history):  # Перебор сообщений в обратном порядке
                # Распаковка данных сообщения в отдельные переменные
                _, model, user_message, ai_response, timestamp, tokens = msg
                # Добавление пары сообщений (пользователь + AI) в интерфейс
                self.chat_history.controls.extend(
                    [
                        MessageBubble(message=user_message, is_user=True),
                        MessageBubble(message=ai_response, is_user=False),
                    ]
                )
        except Exception as e:
            self.logger.error(f"Ошибка загрузки истории чата: {e}")

    def update_balance(self):
        """
        Обновление отображения баланса API и проверка на низкий баланс.
        """
        try:
            balance_str = self.api_client.get_balance()  # Получаем строку вида "$5.00"
            self.balance_text.value = f"Баланс: {balance_str}"
            self.balance_text.color = ft.Colors.GREEN_400

            # Извлекаем число из строки для проверки уведомлений
            balance_value = float(balance_str.replace("$", ""))
            self.notification_manager.notify_low_balance(
                balance_value
            )  # Проверка баланса

        except Exception as e:
            self.balance_text.value = "Баланс: н/д"
            self.balance_text.color = ft.Colors.RED_400
            self.logger.error(f"Ошибка обновления баланса: {e}")

    def main(self, page: ft.Page):
        """
        Основная функция инициализации интерфейса приложения.
        """
        # Применение базовых настроек страницы из конфигурации стилей
        for key, value in AppStyles.PAGE_SETTINGS.items():
            setattr(page, key, value)

        AppStyles.set_window_size(page)  # Установка размеров окна приложения

        # Инициализация выпадающего списка для выбора модели AI
        models = self.api_client.available_models
        self.model_dropdown = ModelSelector(models)
        self.model_dropdown.value = models[0]["id"] if models else None

        async def send_message_click(e):
            if not self.message_input.value:
                return

            try:
                self.message_input.border_color = ft.Colors.BLUE_400
                page.update()

                start_time = time.time()
                user_message = self.message_input.value
                self.message_input.value = ""
                page.update()

                self.chat_history.controls.append(
                    MessageBubble(message=user_message, is_user=True)
                )

                loading = ft.ProgressRing()
                self.chat_history.controls.append(loading)
                page.update()

                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.api_client.send_message(
                        user_message, self.model_dropdown.value
                    ),
                )

                self.chat_history.controls.remove(loading)

                if "error" in response:
                    response_text = f"Ошибка: {response['error']}"
                    tokens_used = 0
                    self.logger.error(f"Ошибка API: {response['error']}")
                else:
                    response_text = response["choices"][0]["message"]["content"]
                    tokens_used = response.get("usage", {}).get("total_tokens", 0)

                self.cache.save_message(
                    model=self.model_dropdown.value,
                    user_message=user_message,
                    ai_response=response_text,
                    tokens_used=tokens_used,
                )

                self.chat_history.controls.append(
                    MessageBubble(message=response_text, is_user=False)
                )

                response_time = time.time() - start_time
                self.analytics.track_message(
                    model=self.model_dropdown.value,
                    message_length=len(user_message),
                    response_time=response_time,
                    tokens_used=tokens_used,
                )

                self.monitor.log_metrics(self.logger)
                page.update()

            except Exception as e:
                self.logger.error(f"Ошибка отправки сообщения: {e}")
                self.message_input.border_color = ft.Colors.RED_500
                show_error_snack(page, str(e))
                page.update()

        def show_error_snack(page, message: str):
            snack = ft.SnackBar(
                content=ft.Text(
                    message, color=ft.Colors.RED_500, weight=ft.FontWeight.BOLD
                ),
                bgcolor=ft.Colors.GREY_900,
                duration=5000,
            )
            page.overlay.append(snack)
            snack.open = True
            page.update()

        async def show_analytics(e):
            stats = self.analytics.get_statistics()
            dialog = ft.AlertDialog(
                title=ft.Text("Аналитика"),
                content=ft.Column(
                    [
                        ft.Text(f"Всего сообщений: {stats['total_messages']}"),
                        ft.Text(f"Всего токенов: {stats['total_tokens']}"),
                        ft.Text(
                            f"Среднее токенов/сообщение: {stats['tokens_per_message']:.2f}"
                        ),
                        ft.Text(
                            f"Сообщений в минуту: {stats['messages_per_minute']:.2f}"
                        ),
                    ]
                ),
                actions=[
                    ft.TextButton("Закрыть", on_click=lambda e: close_dialog(dialog))
                ],
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        async def clear_history(e):
            try:
                self.cache.clear_history()
                self.analytics.clear_data()
                self.chat_history.controls.clear()
            except Exception as e:
                self.logger.error(f"Ошибка очистки истории: {e}")
                show_error_snack(page, f"Ошибка очистки истории: {str(e)}")

        async def confirm_clear_history(e):
            def close_dlg(e):
                close_dialog(dialog)

            async def clear_confirmed(e):
                await clear_history(e)
                close_dialog(dialog)

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Подтверждение удаления"),
                content=ft.Text("Вы уверены? Это действие нельзя отменить!"),
                actions=[
                    ft.TextButton("Отмена", on_click=close_dlg),
                    ft.TextButton("Очистить", on_click=clear_confirmed),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        def close_dialog(dialog):
            dialog.open = False
            page.update()
            if dialog in page.overlay:
                page.overlay.remove(dialog)

        async def save_dialog(e):
            try:
                history = self.cache.get_chat_history()
                dialog_data = []
                for msg in history:
                    dialog_data.append(
                        {
                            "timestamp": msg[4],
                            "model": msg[1],
                            "user_message": msg[2],
                            "ai_response": msg[3],
                            "tokens_used": msg[5],
                        }
                    )

                filename = (
                    f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                filepath = os.path.join(self.exports_dir, filename)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(dialog_data, f, ensure_ascii=False, indent=2, default=str)

                # Определяем команду для открытия папки в зависимости от ОС
                open_cmd = "explorer" if os.name == "nt" else "xdg-open"

                dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Диалог сохранен"),
                    content=ft.Column(
                        [
                            ft.Text("Путь сохранения:"),
                            ft.Text(
                                filepath, selectable=True, weight=ft.FontWeight.BOLD
                            ),
                        ]
                    ),
                    actions=[
                        ft.TextButton("OK", on_click=lambda e: close_dialog(dialog)),
                        ft.TextButton(
                            "Открыть папку",
                            on_click=lambda e: subprocess.run(
                                [open_cmd, self.exports_dir]
                            ),
                        ),
                    ],
                )
                page.overlay.append(dialog)
                dialog.open = True
                page.update()

            except Exception as e:
                self.logger.error(f"Ошибка сохранения: {e}")
                show_error_snack(page, f"Ошибка сохранения: {str(e)}")

        # ==========================================
        # ИСПРАВЛЕННЫЙ БЛОК: Создание компонентов интерфейса
        # ==========================================
        self.message_input = ft.TextField(**AppStyles.MESSAGE_INPUT)
        self.chat_history = ft.ListView(**AppStyles.CHAT_HISTORY)

        self.load_chat_history()

        save_button = ft.FilledButton(on_click=save_dialog, **AppStyles.SAVE_BUTTON)
        clear_button = ft.FilledButton(
            on_click=confirm_clear_history, **AppStyles.CLEAR_BUTTON
        )
        send_button = ft.FilledButton(
            on_click=send_message_click, **AppStyles.SEND_BUTTON
        )
        analytics_button = ft.FilledButton(
            on_click=show_analytics, **AppStyles.ANALYTICS_BUTTON
        )

        control_buttons = ft.Row(
            controls=[save_button, analytics_button, clear_button],
            **AppStyles.CONTROL_BUTTONS_ROW,
        )

        input_row = ft.Row(
            controls=[self.message_input, send_button], **AppStyles.INPUT_ROW
        )

        controls_column = ft.Column(
            controls=[input_row, control_buttons], **AppStyles.CONTROLS_COLUMN
        )

        balance_container = ft.Container(
            content=self.balance_text, **AppStyles.BALANCE_CONTAINER
        )

        model_selection = ft.Column(
            controls=[
                self.model_dropdown.search_field,
                self.model_dropdown,
                balance_container,
            ],
            **AppStyles.MODEL_SELECTION_COLUMN,
        )

        self.main_column = ft.Column(
            controls=[model_selection, self.chat_history, controls_column],
            **AppStyles.MAIN_COLUMN,
        )

        page.add(self.main_column)

        # Запуск монитора и логирование
        self.monitor.get_metrics()
        self.logger.info("Приложение запущено")


def main():
    """Точка входа в приложение"""
    app = ChatApp()
    ft.run(app.main)  # Используем ft.run для Flet 1.0+


if __name__ == "__main__":
    main()
