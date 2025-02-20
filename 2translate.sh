#!/bin/bash

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

echo 'Activating virtual environment...'
source ~/Captioner_Translate/venv/bin/activate

# 检查文件是否已翻译
for file in $files; do
    # 1. 如果存在file.ass，则跳过
    if [ -f "./${file}.ass" ]; then
        echo "INFO: ${file}.ass already exists."
        continue
    fi
    
    # 2. 如果同时存在zh.srt和en.srt，直接生成ass
    if [ -f "./${file}_zh.srt" ] && [ -f "./${file}_en.srt" ]; then
        python3 ~/Captioner_Translate/srt2ass.py "./${file}_zh.srt" "./${file}_en.srt" > /dev/null 2>&1
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
    
    # 调用翻译脚本
    python3 ~/Captioner_Translate/subtitle_translator_cli.py "$input_file" "$@"
    
    # 生成ass字幕文件
    if [ -f "./${file}_zh.srt" ] && [ -f "./${file}_en.srt" ] && [ ! -f "./${file}.ass" ]; then
        python3 ~/Captioner_Translate/srt2ass.py "./${file}_zh.srt" "./${file}_en.srt" > /dev/null 2>&1
        if [ -f "./${file}.ass" ]; then
            echo "INFO: ${file}.ass done."
            rm "./${file}_zh.srt" "./${file}_en.srt"
        fi
    fi
done

echo 'Deactivating virtual environment...'
deactivate