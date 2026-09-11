import pyautogui
import random
import time

# Obter tamanho da tela
screen_width, screen_height = pyautogui.size()

# Define o tempo da movimentação
drag_duration = 2  # segundos

try:
    while True:
        # Posição atual como ponto inicial
        start_x, start_y = pyautogui.position()

        # Vai para o lado direito inferior aleatório
        end_x = random.randint(int(screen_width*0.7), screen_width)
        end_y = random.randint(int(screen_height*0.3), int(screen_height*0.7))
        pyautogui.moveTo(end_x, end_y, duration=drag_duration)

        # Vai para o lado esquerdo superior aleatório
        end_x = random.randint(0, int(screen_width*0.3))
        end_y = random.randint(int(screen_height*0.3), int(screen_height*0.7))
        pyautogui.moveTo(end_x, end_y, duration=drag_duration)

        # Pequena pausa para parecer comportamento humano
        time.sleep(random.uniform(3, 5))

except pyautogui.FailSafeException:
    print("Fail-safe ativado! O mouse foi movido para um canto da tela.")
except KeyboardInterrupt:
    print("\nExecução interrompida manualmente.")
except Exception as e:
    print(f"Erro: {e}")
