#!/bin/bash

2filename.sh 2>/dev/null

en_files=$(ls *_en.srt 2>/dev/null | sed 's/_en[^.]*\.srt$//')
zh_files=$(ls *_zh.srt 2>/dev/null | sed 's/_zh[^.]*\.srt$//')
# 列出当前目录下所有的 .srt 文件，并过滤掉以 _en.srt 和 _zh.srt 结尾的文件
files=$(ls *.srt 2>/dev/null | grep -v '_en\.srt\|_zh\.srt' | sed 's/.srt$//')

# 合并两个文件列表 files 和 en_files，并去除重复的文件名
files=$(echo -e "$files\n$en_files" | awk '!seen[$0]++')

if [ -z "$files" ]; then
    echo "No files to translate."
    exit 1
fi

echo "translating start..."

echo 'Activating virtual environment...'
source ~/VideoCaptioner/venv/bin/activate

# 检查文件是否已翻译
for file in $files; do
    # 如果存在file.ass，则跳过
    if [ -f "./${file}.ass" ]; then
        echo "INFO: ${file}.ass already exists."
        continue
    fi
    # 如果文件不在zh_files中，也不在en_files中
    if [[ ! "$zh_files" =~ (^|[[:space:]])"$file"($|[[:space:]]) && ! "$en_files" =~ (^|[[:space:]])"$file"($|[[:space:]]) ]]; then
        python3 ~/VideoCaptioner/subtitle_translator_cli.py "${file}.srt" "$@"

        # 如果断句生成en，则重命名原来的srt文件
        if [ -f "./${file}_en.srt" ]; then
            mv "./${file}.srt" "./${file}.srt_"
        # 没有断句生成en，则重命名原来的srt文件，为${file}_en.srt
        else
            mv "./${file}.srt" "./${file}_en.srt"
        fi

    # 如果文件不在zh_files中，但在en_files中
    elif [[ ! "$zh_files" =~ (^|[[:space:]])"$file"($|[[:space:]]) && "$en_files" =~ (^|[[:space:]])"$file"($|[[:space:]]) ]]; then
        if [ -f "./${file}.srt" ]; then
            mv "./${file}.srt" "./${file}.srt_"
        fi
        mv "./${file}_en.srt" "./${file}.srt"
        python3 ~/VideoCaptioner/subtitle_translator_cli.py "${file}.srt" "$@"
        mv "./${file}.srt" "./${file}_en.srt"
    else
        echo "INFO: ${file}_zh.srt already translated."
        continue
    fi

    # 生成ass字幕文件
    if [ -f "./${file}_zh.srt" ] && [ -f "./${file}_en.srt" ] && [ ! -f "./${file}.ass" ]; then
        python3 ~/VideoCaptioner/srt2ass.py "./${file}_zh.srt" "./${file}_en.srt" > /dev/null 2>&1
        if [ -f "./${file}.ass" ]; then
            echo "INFO: ${file}.ass done."
            # 软删除srt字幕
            mv "./${file}_en.srt" "./${file}_en.srt_"
            mv "./${file}_zh.srt" "./${file}_zh.srt_"
        fi
    fi
done

# 硬删除srt字幕
# rm -rf *.srt_

echo 'Deactivating virtual environment...'
deactivate