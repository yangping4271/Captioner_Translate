#!/bin/bash

# 初始化计数器和最大执行次数
count=0
max_count=-1  # 默认值-1表示无限制
translator_args=""

# 解析命令行参数
while [ $# -gt 0 ]; do
    case "$1" in
        -n)
            shift
            max_count=$1
            # 验证输入是否为正整数
            if ! [[ "$max_count" =~ ^[0-9]+$ ]]; then
                echo "Error: -n 参数必须是正整数"
                exit 1
            fi
            ;;
        *)
            # 将其他所有参数添加到translator_args
            translator_args="$translator_args $1"
            ;;
    esac
    shift
done

en_files=$(ls *_en.srt 2>/dev/null | sed 's/_en\.srt$//' | sort -V)
# 列出当前目录下所有的 .srt 文件，并过滤掉以 _en.srt 和 _zh.srt 结尾的文件
files=$(ls *.srt 2>/dev/null | grep -v '_en\.srt\|_zh\.srt' | sed 's/.srt$//' | sort -V)

# 合并两个文件列表 files 和 en_files，并去除重复的文件名，保持自然排序
files=$(echo -e "$files\n$en_files" | sort -V | awk '!seen[$0]++')

if [ -z "$files" ]; then
    echo "No files to translate."
    exit 1
fi

echo "translating start..."

# 检测是否使用uv
USE_UV=false
if command -v uv >/dev/null 2>&1 && [ -f ~/Captioner_Translate/pyproject.toml ]; then
    USE_UV=true
    echo "Using uv for Python execution..."
    # 保存当前工作目录
    CURRENT_DIR=$(pwd)
else
    echo "Using virtual environment for Python execution..."
    echo 'Activating virtual environment...'
    source ~/Captioner_Translate/.venv/bin/activate
fi

# 定义运行Python脚本的函数
run_python() {
    local script=$1
    shift
    local args="$@"
    
    if [ "$USE_UV" = true ]; then
        cd ~/Captioner_Translate && uv run "$script" $args && cd - > /dev/null
    else
        python3 ~/Captioner_Translate/"$script" $args
    fi
}

# 检查文件是否已翻译
for file in $files; do
    # 1. 如果存在file.ass，则跳过
    if [ -f "./${file}.ass" ]; then
        echo "INFO: ${file}.ass already exists."
        continue
    fi
    
    # 2. 如果同时存在zh.srt和en.srt，直接生成ass
    if [ -f "./${file}_zh.srt" ] && [ -f "./${file}_en.srt" ]; then
        if [ "$USE_UV" = true ]; then
            run_python srt2ass.py "${CURRENT_DIR}/${file}_zh.srt" "${CURRENT_DIR}/${file}_en.srt" > /dev/null 2>&1
        else
            run_python srt2ass.py "./${file}_zh.srt" "./${file}_en.srt" > /dev/null 2>&1
        fi
        if [ -f "./${file}.ass" ]; then
            echo "INFO: ${file}.ass done."
            rm "./${file}_zh.srt" "./${file}_en.srt"
        fi
        continue
    fi
    
    # 确定输入文件
    input_file=""
    # 3. 如果存在zh.srt但没有en.srt，需要翻译原始字幕
    if [ -f "./${file}_zh.srt" ] && [ ! -f "./${file}_en.srt" ]; then
        if [ -f "./${file}.srt" ]; then
            input_file="./${file}.srt"
        else
            echo "ERROR: No original subtitle found for ${file} with zh.srt"
            continue
        fi
    # 4. 如果存在en.srt，用它翻译
    elif [ -f "./${file}_en.srt" ]; then
        input_file="./${file}_en.srt"
    # 5. 如果只有.srt，用它翻译
    elif [ -f "./${file}.srt" ]; then
        input_file="./${file}.srt"
    else
        echo "ERROR: No input file found for ${file}"
        continue
    fi
    
    # 检查是否达到最大执行次数限制
    if [ $max_count -ne -1 ] && [ $count -ge $max_count ]; then
        echo "已达到最大执行次数限制 ($max_count)"
        break
    fi
    
    # 调用翻译脚本
    if [ "$USE_UV" = true ]; then
        run_python subtitle_translator_cli.py "${CURRENT_DIR}/${input_file}" $translator_args
    else
        run_python subtitle_translator_cli.py "$input_file" $translator_args
    fi
    count=$((count + 1))
    
    # 生成ass字幕文件
    if [ -f "./${file}_zh.srt" ] && [ -f "./${file}_en.srt" ] && [ ! -f "./${file}.ass" ]; then
        if [ "$USE_UV" = true ]; then
            run_python srt2ass.py "${CURRENT_DIR}/${file}_zh.srt" "${CURRENT_DIR}/${file}_en.srt" > /dev/null 2>&1
        else
            run_python srt2ass.py "./${file}_zh.srt" "./${file}_en.srt" > /dev/null 2>&1
        fi
        if [ -f "./${file}.ass" ]; then
            echo "INFO: ${file}.ass done."
            rm "./${file}_zh.srt" "./${file}_en.srt"
        fi
    fi
done

# 清理环境
if [ "$USE_UV" = false ]; then
    echo 'Deactivating virtual environment...'
    deactivate
fi