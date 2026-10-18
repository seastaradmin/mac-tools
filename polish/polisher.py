"""
文字润色模块 - 使用本地语言模型
"""

import os
from typing import Optional, Callable
from pathlib import Path

from config import POLISH_MODEL_NAME, MODEL_CACHE_DIR


class TextPolisher:
    """文字润色类"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        初始化文字润色器
        
        Args:
            model_name: 模型名称，如果为None则使用配置文件中的默认模型
        """
        self.model_name = model_name or POLISH_MODEL_NAME
        self.model = None
        self.tokenizer = None
        self.is_loaded = False
        
        # 回调函数
        self.on_progress_callback: Optional[Callable] = None
        self.on_result_callback: Optional[Callable] = None
    
    def load_model(self) -> bool:
        """
        加载模型
        
        Returns:
            是否加载成功
        """
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            import torch
            
            print(f"正在加载模型: {self.model_name}")
            
            # 检查是否有GPU
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"使用设备: {device}")
            
            # 加载tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=str(MODEL_CACHE_DIR)
            )
            
            # 加载模型
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                cache_dir=str(MODEL_CACHE_DIR),
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None
            )
            
            if device == "cpu":
                self.model = self.model.to(device)
            
            self.is_loaded = True
            print("模型加载完成")
            return True
            
        except Exception as e:
            print(f"模型加载失败: {e}")
            self.is_loaded = False
            return False
    
    def polish_text(self, text: str, style: str = "formal") -> Optional[str]:
        """
        润色文本
        
        Args:
            text: 原始文本
            style: 润色风格 (formal, casual, academic, creative)
            
        Returns:
            润色后的文本
        """
        if not self.is_loaded:
            print("模型未加载，请先调用load_model()")
            return None
        
        # 构建提示词
        prompt = self._build_prompt(text, style)
        
        try:
            import torch
            
            # 编码输入
            inputs = self.tokenizer(prompt, return_tensors="pt")
            
            # 移动到模型所在设备
            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            # 生成回答
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            # 解码输出
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # 提取润色结果（去掉提示词部分）
            polished_text = self._extract_result(response, prompt)
            
            if self.on_result_callback:
                self.on_result_callback(polished_text)
            
            return polished_text
            
        except Exception as e:
            print(f"文本润色失败: {e}")
            return None
    
    def _build_prompt(self, text: str, style: str) -> str:
        """
        构建提示词
        
        Args:
            text: 原始文本
            style: 润色风格
            
        Returns:
            提示词
        """
        style_prompts = {
            "formal": "请将以下文本润色为正式、专业的风格，保持原意不变：",
            "casual": "请将以下文本润色为口语化、自然的风格：",
            "academic": "请将以下文本润色为学术论文风格，使用更专业的词汇：",
            "creative": "请将以下文本润色为更有文采、更生动的风格："
        }
        
        style_desc = style_prompts.get(style, style_prompts["formal"])
        
        prompt = f"""<|system|>
你是一个专业的文本润色助手。{style_desc}
请直接输出润色后的文本，不要添加任何解释。
<|user|>
{text}
<|assistant|>
"""
        return prompt
    
    def _extract_result(self, response: str, prompt: str) -> str:
        """
        从模型响应中提取润色结果
        
        Args:
            response: 完整响应
            prompt: 提示词
            
        Returns:
            润色结果
        """
        # 尝试提取assistant部分
        if "<|assistant|>" in response:
            result = response.split("<|assistant|>")[-1].strip()
            # 去掉可能的结束标记
            if "<|end|>" in result:
                result = result.split("<|end|>")[0].strip()
            return result
        
        # 如果没有找到标记，返回去掉提示词的部分
        if prompt in response:
            return response.replace(prompt, "").strip()
        
        return response.strip()
    
    def polish_with_rules(self, text: str) -> str:
        """
        使用规则进行简单润色（不依赖模型）
        
        Args:
            text: 原始文本
            
        Returns:
            润色后的文本
        """
        import re
        
        # 去除多余空格
        text = re.sub(r'\s+', ' ', text)
        
        # 中文标点修正
        text = text.replace(' ,', '，')
        text = text.replace(' .', '。')
        text = text.replace(' ?', '？')
        text = text.replace(' !', '！')
        text = text.replace(' :', '：')
        text = text.replace(' ;', '；')
        
        # 英文标点修正
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)
        
        # 首字母大写（英文）
        sentences = re.split(r'([.!?]\s+)', text)
        result = []
        for i, sentence in enumerate(sentences):
            if i % 2 == 0 and sentence:  # 句子部分
                sentence = sentence.strip()
                if sentence:
                    sentence = sentence[0].upper() + sentence[1:]
            result.append(sentence)
        text = ''.join(result)
        
        return text.strip()
    
    def set_on_progress_callback(self, callback: Callable):
        """设置进度回调"""
        self.on_progress_callback = callback
    
    def set_on_result_callback(self, callback: Callable):
        """设置结果回调"""
        self.on_result_callback = callback
    
    def is_model_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self.is_loaded
    
    def unload_model(self):
        """卸载模型释放内存"""
        if self.model:
            del self.model
            self.model = None
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None
        self.is_loaded = False
        
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
